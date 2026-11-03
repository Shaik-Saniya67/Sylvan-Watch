"""Locate, load and select trained detectors."""
import json
from pathlib import Path

from sylvan.config import Settings
from sylvan.ml.baseline import SpectralBaseline
from sylvan.ml.detectors import ChangeDetector
from sylvan.ml.random_forest import RandomForestDetector

MODEL_NAMES = ("spectral_baseline", "random_forest", "siamese_unet")
_FILES = {"spectral_baseline": "spectral_baseline.json", "random_forest": "random_forest.joblib",
          "siamese_unet": "siamese_unet.pt"}


class ModelUnavailable(RuntimeError):
    """Raised when a requested model has not been trained or no evaluation exists."""


def artifact_path(settings: Settings, name: str) -> Path:
    return settings.models_dir / _FILES[name]


def available_models(settings: Settings) -> list[str]:
    return [n for n in MODEL_NAMES if artifact_path(settings, n).exists()]


def metrics_path(settings: Settings) -> Path:
    return settings.results_dir / "metrics.json"


def load_metrics(settings: Settings) -> dict | None:
    path = metrics_path(settings)
    return json.loads(path.read_text()) if path.exists() else None


def resolve_model_name(settings: Settings, requested: str) -> str:
    """'best' maps to the model with the highest VALIDATION F1 recorded by the evaluation run."""
    if requested != "best":
        return requested
    metrics = load_metrics(settings)
    if not metrics:
        raise ModelUnavailable("No evaluation has been run yet (storage/results/metrics.json is missing). "
                               "Train and evaluate models first, or choose a model explicitly.")
    return metrics["selected_model"]


def load_detector(settings: Settings, name: str) -> ChangeDetector:
    if name not in MODEL_NAMES:
        raise ModelUnavailable(f"Unknown model '{name}'.")
    path = artifact_path(settings, name)
    if not path.exists():
        raise ModelUnavailable(f"Model '{name}' is not trained: {path} not found. Run scripts/train.py.")
    if name == "spectral_baseline":
        return SpectralBaseline.load(path)
    if name == "random_forest":
        return RandomForestDetector.load(path)
    from sylvan.ml.siamese_detector import SiameseDetector  # torch is imported lazily
    return SiameseDetector.load(path)
