"""A co-registered before/after observation pair and its optional reference labels."""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

from sylvan.constants import CHIP_BANDS, REFLECTANCE_SCALE, S2_BANDS


@dataclass
class Pair:
    """Arrays share one grid. `before`/`after` are (6, H, W) reflectance in [0, 1]."""

    before: np.ndarray
    after: np.ndarray
    valid: np.ndarray        # True where both composites have >= 1 cloud-free observation
    treecover: np.ndarray    # uint8 %, Hansen 2000
    lossyear: np.ndarray     # uint8, Hansen loss year (0 = none)
    landcover: np.ndarray    # uint8, ESA WorldCover class
    transform: Affine
    crs: CRS
    meta: dict = field(default_factory=dict)   # tags: site, years, season, asset versions

    @property
    def shape(self) -> tuple[int, int]:
        return self.valid.shape


def read_chip(path: Path) -> Pair:
    """Load a chip GeoTIFF written by `sylvan.data.chips.write_chip`."""
    with rasterio.open(path) as src:
        if src.count != len(CHIP_BANDS):
            raise ValueError(f"{path} has {src.count} bands, expected {len(CHIP_BANDS)}")
        data = src.read()
        meta = dict(src.tags())
        transform, crs = src.transform, src.crs
    idx = {name: i for i, name in enumerate(CHIP_BANDS)}
    before = data[[idx[f"before_{b}"] for b in S2_BANDS]].astype(np.float32) / REFLECTANCE_SCALE
    after = data[[idx[f"after_{b}"] for b in S2_BANDS]].astype(np.float32) / REFLECTANCE_SCALE
    valid = (data[idx["n_before"]] > 0) & (data[idx["n_after"]] > 0)
    return Pair(
        before=before, after=after, valid=valid,
        treecover=data[idx["treecover2000"]].astype(np.uint8),
        lossyear=data[idx["lossyear"]].astype(np.uint8),
        landcover=data[idx["landcover"]].astype(np.uint8),
        transform=transform, crs=crs, meta=meta,
    )
