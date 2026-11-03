"""Pixel grid and download tiling.

All tiles of one request share a single 10 m UTM grid, so per-tile arrays can be stitched
by integer pixel offsets without resampling.
"""
import math
from dataclasses import dataclass

from rasterio.transform import Affine

from sylvan.constants import PIXEL_SIZE_M, TILE_SIZE_PX
from sylvan.geo.aoi import BBox, to_utm_bounds, utm_epsg


@dataclass(frozen=True)
class Tile:
    row_off: int
    col_off: int
    height: int
    width: int
    xmin: float   # UTM x of the tile's left edge
    ymax: float   # UTM y of the tile's top edge

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) in UTM metres."""
        return (self.xmin, self.ymax - self.height * PIXEL_SIZE_M,
                self.xmin + self.width * PIXEL_SIZE_M, self.ymax)

    @property
    def transform(self) -> Affine:
        return Affine(PIXEL_SIZE_M, 0, self.xmin, 0, -PIXEL_SIZE_M, self.ymax)


@dataclass(frozen=True)
class Grid:
    epsg: int
    xmin: float
    ymax: float
    height: int
    width: int

    @property
    def transform(self) -> Affine:
        return Affine(PIXEL_SIZE_M, 0, self.xmin, 0, -PIXEL_SIZE_M, self.ymax)

    def tiles(self, size: int = TILE_SIZE_PX) -> list[Tile]:
        out = []
        for row in range(0, self.height, size):
            for col in range(0, self.width, size):
                h, w = min(size, self.height - row), min(size, self.width - col)
                out.append(Tile(row, col, h, w, self.xmin + col * PIXEL_SIZE_M, self.ymax - row * PIXEL_SIZE_M))
        return out


def grid_for_bbox(bbox: BBox) -> Grid:
    """Smallest 10 m-aligned UTM grid that covers the bounding box."""
    epsg = utm_epsg(*bbox.center)
    xmin, ymin, xmax, ymax = to_utm_bounds(bbox, epsg)
    xmin = math.floor(xmin / PIXEL_SIZE_M) * PIXEL_SIZE_M
    ymax = math.ceil(ymax / PIXEL_SIZE_M) * PIXEL_SIZE_M
    width = math.ceil((xmax - xmin) / PIXEL_SIZE_M)
    height = math.ceil((ymax - ymin) / PIXEL_SIZE_M)
    return Grid(epsg, xmin, ymax, height, width)
