"""Download real Sentinel-2 / Hansen / WorldCover chips for every site in configs/sites.json.

Usage: python scripts/fetch_chips.py [--sites configs/sites.json] [--only NAME ...]
Existing chips are reused, so the command is resumable. Prints a per-site loss-rate audit:
a site with ~0 Hansen loss is useless for training or testing and should be moved or replaced.
"""
import argparse
from pathlib import Path

from _common import DEFAULT_SITES

from sylvan.config import get_settings
from sylvan.data.chips import fetch_chips
from sylvan.data.gee_client import ChipRequest
from sylvan.geo.aoi import BBox
from sylvan.ml.dataset import load_sites, load_split, split_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites", default=str(DEFAULT_SITES))
    parser.add_argument("--only", nargs="*", help="restrict to these site names")
    args = parser.parse_args()

    settings = get_settings()
    sites = load_sites(Path(args.sites))
    for site in sites:
        if args.only and site.name not in args.only:
            continue
        print(f"[{site.split}] {site.name}: fetching ...")
        request = ChipRequest(site.before_year, site.after_year, site.season_months)
        fetch_chips(settings, BBox(*site.bbox), request, settings.chips_dir / site.name, site.name,
                    extra_tags={"site": site.name}, skip_small=True,
                    on_tile=lambda i, n: print(f"   tile {i}/{n}", end="\r"))
    print("\nLoss-rate audit (Hansen, forest pixels only):")
    for split in ("train", "val", "test"):
        summary = split_summary(load_split(settings, sites, split), settings.tree_cover_threshold)
        rate = summary["loss_rate"]
        print(f"  {split:5s} tiles={summary['tiles']:3d} loss_pixels={summary['loss_pixels']:>9,d} "
              f"loss_rate={'n/a' if rate is None else f'{100 * rate:.3f}%'}")
        if rate is not None and rate < 0.001:
            print(f"        WARNING: {split} loss rate below 0.1%; metrics will be unreliable. Revisit site boxes.")


if __name__ == "__main__":
    main()
