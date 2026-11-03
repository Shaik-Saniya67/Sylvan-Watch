"""Train the spectral baseline and the Random Forest on the training chips."""
from sylvan.config import Settings
from sylvan.ml.baseline import SpectralBaseline
from sylvan.ml.labels import pair_labels
from sylvan.ml.pair import Pair
from sylvan.ml.random_forest import RandomForestDetector, sample_training_pixels


def train_classical(settings: Settings, train: list[Pair], seed: int = 42) -> dict:
    """Fit both classical detectors using training chips only; returns a summary for the report."""
    labelled = [pair_labels(p, settings.tree_cover_threshold) for p in train]
    targets, domains = [loss for loss, _ in labelled], [domain for _, domain in labelled]
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = settings.models_dir / "spectral_baseline.json"
    if baseline_path.exists():
        # Keep a previously saved spectral baseline; only Random Forest is (re)fit.
        baseline = SpectralBaseline.load(baseline_path)
        baseline_info = {
            "dnbr_threshold": baseline.dnbr_threshold,
            "dndvi_threshold": baseline.dndvi_threshold,
            "reused_existing": True,
        }
    else:
        baseline = SpectralBaseline().fit(train, targets, domains)
        baseline.save(baseline_path)
        baseline_info = {
            "dnbr_threshold": baseline.dnbr_threshold,
            "dndvi_threshold": baseline.dndvi_threshold,
            "reused_existing": False,
        }

    x, y = sample_training_pixels(train, targets, domains, seed)
    forest = RandomForestDetector().fit(x, y, seed)
    forest.save(settings.models_dir / "random_forest.joblib")
    return {
        "baseline": baseline_info,
        "random_forest": {"training_pixels": int(len(y)), "positive_pixels": int(y.sum()), "seed": seed},
    }
