"""Approach A: spectral-index change baseline (dNBR and dNDVI thresholds).

A pixel is flagged when both NBR and NDVI dropped by more than fitted thresholds.
Thresholds are the grid-search maximum of F1 on the TRAINING chips only.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sylvan.ml.indices import nbr, ndvi
from sylvan.ml.metrics import confusion, scores
from sylvan.ml.pair import Pair


@dataclass
class SpectralBaseline:
    dnbr_threshold: float = 0.2
    dndvi_threshold: float = 0.15
    name: str = "spectral_baseline"
    calibrated_probability: bool = False

    def predict_score(self, pair: Pair) -> np.ndarray:
        d_nbr = nbr(pair.before) - nbr(pair.after)
        d_ndvi = ndvi(pair.before) - ndvi(pair.after)
        flagged = (d_nbr > self.dnbr_threshold) & (d_ndvi > self.dndvi_threshold) & pair.valid
        return flagged.astype(np.float32)

    def fit(self, pairs: list[Pair], targets: list[np.ndarray], domains: list[np.ndarray]) -> "SpectralBaseline":
        """Grid-search thresholds (step 0.025) maximising pooled F1 on the training chips."""
        deltas = [(nbr(p.before) - nbr(p.after), ndvi(p.before) - ndvi(p.after)) for p in pairs]
        best = (-1.0, self.dnbr_threshold, self.dndvi_threshold)
        for t_nbr in np.arange(0.05, 0.60, 0.025):
            for t_ndvi in np.arange(0.05, 0.60, 0.025):
                total = None
                for (d_nbr, d_ndvi), target, domain in zip(deltas, targets, domains, strict=True):
                    c = confusion((d_nbr > t_nbr) & (d_ndvi > t_ndvi), target, domain)
                    total = c if total is None else total + c
                f1 = scores(total)["f1"]
                if f1 > best[0]:
                    best = (f1, float(t_nbr), float(t_ndvi))
        self.dnbr_threshold, self.dndvi_threshold = round(best[1], 3), round(best[2], 3)
        return self

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"dnbr_threshold": self.dnbr_threshold, "dndvi_threshold": self.dndvi_threshold}))

    @classmethod
    def load(cls, path: Path) -> "SpectralBaseline":
        return cls(**json.loads(path.read_text()))
