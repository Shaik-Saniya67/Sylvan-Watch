"""Evaluate every trained model on held-out test sites and write storage/results/metrics.json.

Usage: python scripts/evaluate.py [--reference my_polygons.geojson]
The optional reference file holds independently digitised polygons (properties.kind = loss | stable).
"""
import argparse
from pathlib import Path

from _common import DEFAULT_SITES

from sylvan.config import get_settings
from sylvan.ml.dataset import load_sites
from sylvan.ml.evaluation import evaluate_all


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=None)
    args = parser.parse_args()
    report = evaluate_all(get_settings(), load_sites(DEFAULT_SITES), args.reference)
    print(f"Selected by validation F1: {report['selected_model']}")
    for name, m in report["models"].items():
        t = m["test"]
        print(f"  {name:18s} test F1 {t['f1']:.3f}  P {t['precision']:.3f}  R {t['recall']:.3f}  IoU {t['iou']:.3f}  thr {m['threshold']}")


if __name__ == "__main__":
    main()
