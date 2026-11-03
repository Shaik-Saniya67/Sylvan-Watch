"""Test fixtures.

NOTE: the arrays built here are *unit-test inputs* used to check the arithmetic of the code
(indices, labels, metrics, geometry). They are never used for training, evaluation or the app.
"""
import os
import tempfile

os.environ["SYLVAN_STORAGE_DIR"] = tempfile.mkdtemp(prefix="sylvan-test-")

import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import Affine

from sylvan.constants import S2_BANDS
from sylvan.ml.pair import Pair

CLEARED = (slice(20, 52), slice(24, 56))    # 32 x 32 px block that is cleared between dates


def build_pair(size: int = 64) -> Pair:
    """size x size pair: forest everywhere; one block loses canopy (Hansen loss year 2021)."""
    rng = np.random.default_rng(0)
    block = (slice(size * 5 // 16, size * 13 // 16), slice(size * 3 // 8, size * 7 // 8))
    forest = np.zeros((len(S2_BANDS), size, size), np.float32)
    # order B2,B3,B4,B8,B11,B12: dense canopy = low visible, high NIR, low SWIR
    for i, value in enumerate((0.03, 0.05, 0.03, 0.40, 0.18, 0.08)):
        forest[i] = value
    before = forest + rng.normal(0, 0.003, forest.shape).astype(np.float32)
    after = before.copy()
    for i, value in enumerate((0.08, 0.10, 0.12, 0.22, 0.30, 0.25)):   # bare soil
        after[(i, *block)] = value
    lossyear = np.zeros((size, size), np.uint8)
    lossyear[block] = 21
    return Pair(
        before=before, after=after, valid=np.ones((size, size), bool),
        treecover=np.full((size, size), 80, np.uint8), lossyear=lossyear,
        landcover=np.full((size, size), 10, np.uint8),
        transform=Affine(10, 0, 500000, 0, -10, 1000000), crs=CRS.from_epsg(32644),
        meta={"before_year": "2019", "after_year": "2023", "site": "unit"},
    )


@pytest.fixture
def pair() -> Pair:
    return build_pair(64)


def pair_to_chip(path, pair: Pair) -> None:
    """Write a Pair as a chip GeoTIFF (test helper)."""
    from sylvan.constants import CHIP_BANDS, REFLECTANCE_SCALE
    from sylvan.data.chips import write_chip

    h, w = pair.shape
    data = np.zeros((len(CHIP_BANDS), h, w), np.int16)
    for i, name in enumerate(CHIP_BANDS):
        if name.startswith("before_"):
            data[i] = pair.before[i] * REFLECTANCE_SCALE
        elif name.startswith("after_"):
            data[i] = pair.after[i - 6] * REFLECTANCE_SCALE
    data[CHIP_BANDS.index("n_before")] = data[CHIP_BANDS.index("n_after")] = 3
    data[CHIP_BANDS.index("treecover2000")] = pair.treecover
    data[CHIP_BANDS.index("lossyear")] = pair.lossyear
    data[CHIP_BANDS.index("landcover")] = pair.landcover
    write_chip(path, data, pair.transform, pair.crs, {"before_year": pair.meta["before_year"], "after_year": pair.meta["after_year"]})
