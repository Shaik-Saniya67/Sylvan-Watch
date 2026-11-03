"""Area computation from real pixel geometry."""
import numpy as np
from rasterio.crs import CRS
from rasterio.transform import Affine


def pixel_area_ha(transform: Affine, crs: CRS) -> float:
    """Area of one pixel in hectares. Requires a projected CRS (metres)."""
    if not crs.is_projected:
        raise ValueError("Pixel area requires a projected CRS; reproject to UTM first.")
    return abs(transform.a * transform.e - transform.b * transform.d) / 10_000.0


def mask_area_ha(mask: np.ndarray, transform: Affine, crs: CRS) -> float:
    """Total area (ha) of True pixels."""
    return float(mask.sum()) * pixel_area_ha(transform, crs)
