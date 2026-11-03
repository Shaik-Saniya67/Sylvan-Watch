"""Segmentation metrics, tile-bootstrap confidence intervals and calibration."""
from dataclasses import dataclass

import numpy as np


@dataclass
class Confusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def __add__(self, other: "Confusion") -> "Confusion":
        return Confusion(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn, self.tn + other.tn)

    def as_matrix(self) -> list[list[int]]:
        """Rows = reference [stable, loss]; columns = predicted [stable, loss]."""
        return [[self.tn, self.fp], [self.fn, self.tp]]


def confusion(pred: np.ndarray, target: np.ndarray, domain: np.ndarray) -> Confusion:
    """Confusion counts restricted to `domain` pixels."""
    p, t = pred.astype(bool)[domain], target.astype(bool)[domain]
    return Confusion(
        tp=int((p & t).sum()), fp=int((p & ~t).sum()), fn=int((~p & t).sum()), tn=int((~p & ~t).sum())
    )


def _ratio(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def scores(c: Confusion) -> dict:
    """Precision, recall, F1 and IoU for the loss class, IoU for stable, and class-wise breakdown."""
    loss_precision, loss_recall = _ratio(c.tp, c.tp + c.fp), _ratio(c.tp, c.tp + c.fn)
    stable_precision, stable_recall = _ratio(c.tn, c.tn + c.fn), _ratio(c.tn, c.tn + c.fp)
    f1 = _ratio(2 * loss_precision * loss_recall, loss_precision + loss_recall)
    iou_loss, iou_stable = _ratio(c.tp, c.tp + c.fp + c.fn), _ratio(c.tn, c.tn + c.fp + c.fn)
    return {
        "precision": loss_precision, "recall": loss_recall, "f1": f1, "iou": iou_loss,
        "mean_iou": (iou_loss + iou_stable) / 2,
        "accuracy": _ratio(c.tp + c.tn, c.tp + c.tn + c.fp + c.fn),
        "classwise": {
            "loss": {"precision": loss_precision, "recall": loss_recall, "iou": iou_loss},
            "stable": {"precision": stable_precision, "recall": stable_recall, "iou": iou_stable},
        },
        "confusion_matrix": c.as_matrix(),
        "support": {"loss_pixels": c.tp + c.fn, "stable_pixels": c.tn + c.fp},
    }


def bootstrap_f1(per_tile: list[Confusion], n_boot: int = 500, seed: int = 0) -> tuple[float, float]:
    """95% interval of pooled F1 from resampling whole tiles (respects spatial clustering)."""
    if len(per_tile) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_boot):
        picks = rng.integers(0, len(per_tile), len(per_tile))
        total = Confusion()
        for i in picks:
            total = total + per_tile[i]
        values.append(scores(total)["f1"])
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


class CalibrationAccumulator:
    """Streaming Brier score and expected calibration error (ECE) over 10 probability bins."""

    def __init__(self, bins: int = 10) -> None:
        self.edges = np.linspace(0, 1, bins + 1)
        self.count = np.zeros(bins)
        self.positives = np.zeros(bins)
        self.prob_sum = np.zeros(bins)
        self.sq_err = 0.0
        self.total = 0

    def update(self, prob: np.ndarray, target: np.ndarray, domain: np.ndarray) -> None:
        p, t = prob[domain].astype(np.float64), target[domain].astype(np.float64)
        bin_ids = np.clip(np.digitize(p, self.edges[1:-1]), 0, len(self.count) - 1)
        self.count += np.bincount(bin_ids, minlength=len(self.count))
        self.positives += np.bincount(bin_ids, weights=t, minlength=len(self.count))
        self.prob_sum += np.bincount(bin_ids, weights=p, minlength=len(self.count))
        self.sq_err += float(((p - t) ** 2).sum())
        self.total += p.size

    def result(self) -> dict:
        if not self.total:
            return {"brier": None, "ece": None}
        used = self.count > 0
        gap = np.abs(self.positives[used] / self.count[used] - self.prob_sum[used] / self.count[used])
        return {"brier": self.sq_err / self.total, "ece": float((gap * self.count[used]).sum() / self.total)}
