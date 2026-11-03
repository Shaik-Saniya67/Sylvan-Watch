"""Spectral indices computed from Sentinel-2 surface reflectance (0-1 floats)."""
import numpy as np

from sylvan.constants import BAND_INDEX

_EPS = 1e-6


def _normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a - b) / (a + b + _EPS)


def ndvi(bands: np.ndarray) -> np.ndarray:
    """Vegetation greenness: (NIR - Red) / (NIR + Red)."""
    return _normalized_difference(bands[BAND_INDEX["B8"]], bands[BAND_INDEX["B4"]])


def nbr(bands: np.ndarray) -> np.ndarray:
    """Normalized Burn Ratio: (NIR - SWIR2) / (NIR + SWIR2); drops sharply after canopy removal."""
    return _normalized_difference(bands[BAND_INDEX["B8"]], bands[BAND_INDEX["B12"]])


def ndmi(bands: np.ndarray) -> np.ndarray:
    """Moisture index: (NIR - SWIR1) / (NIR + SWIR1); sensitive to canopy water content."""
    return _normalized_difference(bands[BAND_INDEX["B8"]], bands[BAND_INDEX["B11"]])


def index_stack(bands: np.ndarray) -> np.ndarray:
    """(3, H, W) stack of NDVI, NBR, NDMI."""
    return np.stack([ndvi(bands), nbr(bands), ndmi(bands)])
