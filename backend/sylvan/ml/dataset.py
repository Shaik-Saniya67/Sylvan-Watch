"""Site configuration and chip loading with site-level train/val/test separation.

Whole sites (not random tiles) are assigned to a split, so no test pixel has a training pixel
as a spatial neighbour. This is the main defence against spatial autocorrelation leakage.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from sylvan.config import Settings
from sylvan.ml.labels import pair_labels
from sylvan.ml.pair import Pair, read_chip

SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class Site:
    name: str
    bbox: tuple[float, float, float, float]   # west, south, east, north (WGS84)
    split: str
    season_months: tuple[int, int]            # inclusive months within one calendar year
    before_year: int
    after_year: int
    note: str = ""


def load_sites(path: Path) -> list[Site]:
    raw = json.loads(path.read_text())
    sites = [Site(**{**s, "bbox": tuple(s["bbox"]), "season_months": tuple(s["season_months"])}) for s in raw["sites"]]
    bad = [s.name for s in sites if s.split not in SPLITS]
    if bad:
        raise ValueError(f"Sites with invalid split (use train/val/test): {bad}")
    return sites


def load_split(settings: Settings, sites: list[Site], split: str) -> list[Pair]:
    """All chips of every site assigned to `split`. Each Pair.meta carries its site name."""
    pairs = []
    for site in (s for s in sites if s.split == split):
        for path in sorted((settings.chips_dir / site.name).glob("*.tif")):
            pair = read_chip(path)
            pair.meta["site"] = site.name
            pairs.append(pair)
    return pairs


def split_summary(pairs: list[Pair], tree_threshold: int) -> dict:
    """Counts used in the performance report (tiles, forest pixels, loss pixels, loss rate)."""
    domain_px = loss_px = 0
    for pair in pairs:
        loss, domain = pair_labels(pair, tree_threshold)
        domain_px, loss_px = domain_px + int(domain.sum()), loss_px + int(loss.sum())
    return {
        "tiles": len(pairs), "sites": sorted({p.meta["site"] for p in pairs}),
        "forest_pixels": domain_px, "loss_pixels": loss_px,
        "loss_rate": (loss_px / domain_px) if domain_px else None,
    }
