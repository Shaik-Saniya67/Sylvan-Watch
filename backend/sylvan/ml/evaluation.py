"""Compare all trained detectors on the same held-out test sites.

Protocol: the decision threshold of each probabilistic model is chosen on VALIDATION chips only;
test chips are used once for reporting; the "selected" model is chosen by validation F1.
"""
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from sylvan.config import Settings
from sylvan.ml.dataset import Site, load_split, split_summary
from sylvan.ml.detectors import ChangeDetector
from sylvan.ml.labels import pair_labels
from sylvan.ml.metrics import CalibrationAccumulator, Confusion, bootstrap_f1, confusion, scores
from sylvan.ml.pair import Pair
from sylvan.ml.reference_validation import load_reference, score_against_reference
from sylvan.ml.registry import available_models, load_detector

CAVEATS = [
    "Labels come from Hansen Global Forest Change (Landsat-derived, 30 m, annual). Scores measure agreement "
    "with that reference product, not field-verified accuracy.",
    "Hansen counts plantation harvest and fire as loss, so some 'false positives' may be correct detections of "
    "legal harvesting or burns; imagery alone cannot establish legality.",
    "Metrics hold for the evaluated sites, seasons and years only; no global generalisation is claimed.",
    "Selective logging of individual trees is below the detection limit of 10 m optical imagery.",
]


def _select_threshold(maps: list[np.ndarray], labelled: list[tuple[np.ndarray, np.ndarray]], calibrated: bool) -> float:
    """Pooled-F1-maximising threshold on validation data (0.5 for rule-based detectors)."""
    if not calibrated:
        return 0.5
    best_f1, best_t = -1.0, 0.5
    for t in np.arange(0.05, 0.96, 0.05):
        total = Confusion()
        for score, (target, domain) in zip(maps, labelled, strict=True):
            total = total + confusion(score >= t, target, domain)
        f1 = scores(total)["f1"]
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    return round(best_t, 2)


def _pool(maps, labelled, threshold) -> tuple[Confusion, list[Confusion]]:
    per_tile = [confusion(m >= threshold, t, d) for m, (t, d) in zip(maps, labelled, strict=True)]
    return sum(per_tile, Confusion()), per_tile


def _clean(value):
    """Make NaN/inf JSON-safe."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _evaluate_detector(detector: ChangeDetector, val: list[Pair], test: list[Pair], settings: Settings, reference) -> dict:
    thr = settings.tree_cover_threshold
    val_labels = [pair_labels(p, thr) for p in val]
    test_labels = [pair_labels(p, thr) for p in test]
    val_maps = [detector.predict_score(p) for p in val]
    test_maps = [detector.predict_score(p) for p in test]

    threshold = _select_threshold(val_maps, val_labels, detector.calibrated_probability)
    val_total, _ = _pool(val_maps, val_labels, threshold)
    test_total, per_tile = _pool(test_maps, test_labels, threshold)

    per_site: dict[str, Confusion] = {}
    for pair, c in zip(test, per_tile, strict=True):
        per_site[pair.meta["site"]] = per_site.get(pair.meta["site"], Confusion()) + c

    calibration = None
    if detector.calibrated_probability:
        acc = CalibrationAccumulator()
        for score, (target, domain) in zip(test_maps, test_labels, strict=True):
            acc.update(score, target, domain)
        calibration = acc.result()

    lo, hi = bootstrap_f1(per_tile)
    result = {
        "threshold": threshold,
        "validation": scores(val_total),
        "test": {**scores(test_total), "f1_ci95_tile_bootstrap": [lo, hi]},
        "per_site_test": {site: scores(c) for site, c in per_site.items()},
        "calibration": calibration,
        "independent_reference": None,
    }
    if reference is not None:
        result["independent_reference"] = scores(score_against_reference(test, test_maps, threshold, reference))
    return result


def evaluate_all(settings: Settings, sites: list[Site], reference_path: Path | None = None) -> dict:
    """Evaluate every trained model; writes and returns storage/results/metrics.json content."""
    val, test = load_split(settings, sites, "val"), load_split(settings, sites, "test")
    if not val or not test:
        raise ValueError("Need chips for at least one validation site and one test site; run scripts/fetch_chips.py.")
    names = available_models(settings)
    if not names:
        raise ValueError("No trained models found in storage/models; run scripts/train.py first.")
    reference = load_reference(reference_path) if reference_path else None

    models = {name: _evaluate_detector(load_detector(settings, name), val, test, settings, reference) for name in names}
    selected = max(models, key=lambda n: models[n]["validation"]["f1"])
    history_path = settings.results_dir / "training_history.json"
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "label_source": "Hansen Global Forest Change (reference product; not field ground truth)",
        "datasets": {
            "hansen": settings.hansen_asset, "sentinel2": settings.s2_asset, "worldcover": settings.worldcover_asset,
            "tree_cover_threshold_percent": settings.tree_cover_threshold,
        },
        "sites": [s.__dict__ | {"bbox": list(s.bbox), "season_months": list(s.season_months)} for s in sites],
        "splits": {
            "train": split_summary(load_split(settings, sites, "train"), settings.tree_cover_threshold),
            "val": split_summary(val, settings.tree_cover_threshold),
            "test": split_summary(test, settings.tree_cover_threshold),
        },
        "split_strategy": "Whole sites are assigned to train, validation or test, so no test pixel neighbours a training pixel.",
        "data_notes": [
            "seshachalam_ap is an incomplete download (26 chips on disk; other sites have full 6x6 or 5x6 grids). "
            "Its per-site test scores are reported separately and must not be treated as a complete-site result.",
            "Hansen experiment window is 2019-2023. lossyear encoding: 20-23 = calendar years 2020-2023 "
            "(loss in (before_year, after_year] with before_year=2019 and after_year=2023).",
            "Class imbalance is severe on hasdeo_arand (validation) and seshachalam_ap (test); pooled test metrics "
            "are dominated by rondonia_b.",
        ],
        "models": models,
        "selected_model": selected,
        "selection_criterion": "Highest validation F1 (test data were not used for selection or thresholds).",
        "training_history": json.loads(history_path.read_text()) if history_path.exists() else None,
        "caveats": CAVEATS,
    }
    report = _clean(report)
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    (settings.results_dir / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    return report
