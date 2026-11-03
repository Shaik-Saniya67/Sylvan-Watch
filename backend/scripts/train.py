"""Train detectors on training chips (validation chips are used only for early stopping).

Usage: python scripts/train.py [--models baseline_rf siamese] [--seed 42] [--epochs 40]
"""
import argparse
import json

from _common import DEFAULT_SITES

from sylvan.config import get_settings
from sylvan.ml.dataset import load_sites, load_split
from sylvan.ml.training_classical import train_classical


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["baseline_rf", "siamese"], choices=["baseline_rf", "siamese"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args()

    settings = get_settings()
    sites = load_sites(DEFAULT_SITES)
    train, val = load_split(settings, sites, "train"), load_split(settings, sites, "val")
    if not train or not val:
        raise SystemExit("No training/validation chips found. Run scripts/fetch_chips.py first.")
    settings.results_dir.mkdir(parents=True, exist_ok=True)

    if "baseline_rf" in args.models:
        print("Training spectral baseline and Random Forest ...")
        print(json.dumps(train_classical(settings, train, args.seed), indent=2))
    if "siamese" in args.models:
        from sylvan.ml.training_siamese import train_siamese  # imports torch
        print("Training Siamese U-Net ...")
        info = train_siamese(settings, train, val, seed=args.seed, epochs=args.epochs)
        (settings.results_dir / "training_history.json").write_text(json.dumps(info, indent=2))
        print(f"Best validation F1 (threshold 0.5): {info['best_val_f1']:.4f} on {info['device']}")


if __name__ == "__main__":
    main()
