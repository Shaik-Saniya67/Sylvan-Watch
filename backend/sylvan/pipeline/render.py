"""Turn arrays into web-ready previews (PNG) and their WGS84 corner coordinates."""
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer

from sylvan.constants import BAND_INDEX
from sylvan.geo.tiling import Grid


def true_color_png(bands: np.ndarray, valid: np.ndarray, path: Path) -> None:
    """RGB preview with a 2-98 percentile stretch computed over valid pixels."""
    rgb = np.stack([bands[BAND_INDEX[b]] for b in ("B4", "B3", "B2")], axis=-1)
    out = np.zeros(rgb.shape, dtype=np.uint8)
    if valid.any():
        lo, hi = np.percentile(rgb[valid], [2, 98], axis=0)
        out = np.clip((rgb - lo) / np.maximum(hi - lo, 1e-6), 0, 1)
        out = (out * 255).astype(np.uint8)
    alpha = np.where(valid, 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack([out, alpha]), "RGBA").save(path)


def change_overlay_png(mask: np.ndarray, score: np.ndarray, path: Path) -> None:
    """Coral RGBA overlay of detected loss pixels; opacity follows the model score (min 55%)."""
    alpha = np.where(mask, np.clip(140 + 115 * score, 0, 255), 0).astype(np.uint8)
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3] = 255, 99, 88, alpha
    Image.fromarray(rgba, "RGBA").save(path)


def wgs84_corners(grid: Grid) -> list[list[float]]:
    """[top-left, top-right, bottom-right, bottom-left] as [lon, lat], the order MapLibre image sources expect."""
    to_wgs = Transformer.from_crs(grid.epsg, 4326, always_xy=True)
    x0, y1 = grid.xmin, grid.ymax
    x1, y0 = grid.xmin + grid.width * 10, grid.ymax - grid.height * 10
    return [list(to_wgs.transform(x, y)) for x, y in ((x0, y1), (x1, y1), (x1, y0), (x0, y0))]
