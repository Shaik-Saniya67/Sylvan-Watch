"""Verbose Random Forest training with stage logs. Uses the existing train_classical path."""
import traceback
from pathlib import Path

from _common import DEFAULT_SITES

from sylvan.config import get_settings
from sylvan.ml.dataset import load_sites, load_split
from sylvan.ml.training_classical import train_classical


def main() -> None:
    print("loading settings/sites", flush=True)
    settings = get_settings()
    sites = load_sites(DEFAULT_SITES)
    print("loading train split", flush=True)
    train = load_split(settings, sites, "train")
    print(f"train chips={len(train)}", flush=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    try:
        info = train_classical(settings, train, 42)
        print("train_classical done", info, flush=True)
        rf = settings.models_dir / "random_forest.joblib"
        print("artifact exists", rf.exists(), "size", rf.stat().st_size if rf.exists() else None, flush=True)
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
