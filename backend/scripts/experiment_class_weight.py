"""Final controlled Random Forest candidate experiment."""
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

import numpy as np

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import DEFAULT_SITES
from sylvan.config import get_settings
from sylvan.ml.dataset import load_sites, load_split
from sylvan.ml.labels import pair_labels
from sylvan.ml.metrics import Confusion, confusion, scores
from sylvan.ml.random_forest import RandomForestDetector, sample_training_pixels

SEED = 42
THRESHOLD = 0.55
CANDIDATE_TREES = 200
CANDIDATE_LEAF_SIZE = 3
CANDIDATE_FILENAME = "random_forest_final_candidate.joblib"
REPORT_FILENAME = "final_candidate_experiment.json"


def evaluate_on_validation(detector, val_pairs, val_labels):
    maps = [detector.predict_score(pair) for pair in val_pairs]

    per_tile = [
        confusion(score_map >= THRESHOLD, target, domain)
        for score_map, (target, domain) in zip(
            maps, val_labels, strict=True
        )
    ]

    pooled = sum(per_tile, Confusion())
    per_site = {}

    for pair, tile_confusion in zip(val_pairs, per_tile, strict=True):
        site = pair.meta["site"]
        per_site[site] = per_site.get(site, Confusion()) + tile_confusion

    return {
        "threshold": THRESHOLD,
        "pooled": scores(pooled),
        "per_site": {
            site: scores(value) for site, value in per_site.items()
        },
    }


def main():
    settings = get_settings()
    sites = load_sites(DEFAULT_SITES)

    train = load_split(settings, sites, "train")
    val = load_split(settings, sites, "val")

    if not train or not val:
        raise SystemExit("Training or validation data is missing.")

    train_sites = sorted({p.meta.get("site") for p in train})
    val_sites = sorted({p.meta.get("site") for p in val})

    forbidden = {"rondonia_b", "seshachalam_ap"}
    if forbidden.intersection(train_sites + val_sites):
        raise SystemExit("Test site detected. Aborting.")

    print("Training sites:", train_sites)
    print("Validation sites:", val_sites)

    labelled = [
        pair_labels(pair, settings.tree_cover_threshold)
        for pair in train
    ]
    targets = [loss for loss, _ in labelled]
    domains = [domain for _, domain in labelled]

    print("\nSampling training pixels with seed 42...")
    x, y = sample_training_pixels(train, targets, domains, seed=SEED)

    positive = int(y.sum())
    negative = int(len(y) - positive)

    print(f"Pixels: {len(y):,}")
    print(f"Positive: {positive:,}")
    print(f"Negative: {negative:,}")
    print(f"Features: {x.shape[1]}")

    if x.shape[1] != 27:
        raise SystemExit("Expected 27 features. Aborting.")

    candidate_path = settings.models_dir / CANDIDATE_FILENAME
    report_path = settings.results_dir / REPORT_FILENAME

    if candidate_path.exists() or report_path.exists():
        raise SystemExit(
            "Candidate model or report already exists. Nothing overwritten."
        )

    print("\nTraining candidate: 200 trees, leaf size 3, class_weight=None")

    candidate = RandomForestDetector(name="random_forest_final_candidate")
    candidate.fit(
        x,
        y,
        seed=SEED,
        class_weight=None,
        n_estimators=CANDIDATE_TREES,
        min_samples_leaf=CANDIDATE_LEAF_SIZE,
    )

    candidate.save(candidate_path)
    reloaded = RandomForestDetector.load(candidate_path)

    if reloaded.model is None:
        raise SystemExit("Model reload verification failed.")

    print("Candidate saved and reload verified.")

    print("\nEvaluating validation data only...")
    val_labels = [
        pair_labels(pair, settings.tree_cover_threshold)
        for pair in val
    ]

    results = evaluate_on_validation(reloaded, val, val_labels)

    report = {
        "experiment": "final_random_forest_candidate",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "training": {
            "sites": train_sites,
            "seed": SEED,
            "features": int(x.shape[1]),
            "total_pixels": int(len(y)),
            "positive_pixels": positive,
            "negative_pixels": negative,
            "class_weight": None,
            "n_estimators": CANDIDATE_TREES,
            "min_samples_leaf": CANDIDATE_LEAF_SIZE,
        },
        "validation": {
            "sites": val_sites,
            "chips": len(val),
            **results,
        },
        "saved_model": CANDIDATE_FILENAME,
        "test_data_accessed": False,
    }

    settings.results_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    print("\n=== CANDIDATE VALIDATION RESULTS ===")
    for metric in ("accuracy", "precision", "recall", "f1", "iou"):
        print(f"{metric.capitalize():<12}: {results['pooled'][metric]:.4f}")

    print("\nPer-site results:")
    for site, metrics in results["per_site"].items():
        print(f"\n{site}")
        for metric in ("accuracy", "precision", "recall", "f1", "iou"):
            print(f"  {metric.capitalize():<12}: {metrics[metric]:.4f}")

    print(f"\nModel: {candidate_path}")
    print(f"Report: {report_path}")
    print("Test data accessed: NO")
    print("Existing models overwritten: NO")


if __name__ == "__main__":
    main()
