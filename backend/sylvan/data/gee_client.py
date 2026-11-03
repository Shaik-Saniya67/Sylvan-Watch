"""Google Earth Engine access: authentication, composite construction and tile download.

Nothing here fabricates data: if Earth Engine cannot be reached the caller gets an
EarthEngineUnavailable error with setup instructions.
"""
import logging
import time
from dataclasses import dataclass

import httpx

from sylvan.config import Settings
from sylvan.constants import CHIP_BANDS, PIXEL_SIZE_M, S2_BANDS
from sylvan.geo.tiling import Tile

log = logging.getLogger(__name__)
_SETUP_HELP = (
    "Run `earthengine authenticate` and set SYLVAN_EE_PROJECT to a Cloud project registered for Earth Engine, "
    "or set SYLVAN_EE_SERVICE_ACCOUNT and SYLVAN_EE_PRIVATE_KEY_FILE. See README, 'Earth Engine setup'."
)
# SCL classes removed: 0 no data, 1 saturated, 3 cloud shadow, 8/9 cloud, 10 cirrus, 11 snow/ice.
# Class 2 (dark area) is kept: in hilly forest it is mostly terrain shadow, not cloud.
_SCL_MASKED = (0, 1, 3, 8, 9, 10, 11)
_ee = None


class EarthEngineUnavailable(RuntimeError):
    """Raised when Earth Engine cannot be imported, authenticated or queried."""


@dataclass(frozen=True)
class ChipRequest:
    before_year: int
    after_year: int
    season_months: tuple[int, int]   # inclusive, within one calendar year


def initialize(settings: Settings):
    """Initialise (once) and return the `ee` module."""
    global _ee
    if _ee is not None:
        return _ee
    try:
        import ee
    except ImportError as exc:
        raise EarthEngineUnavailable("The earthengine-api package is not installed. " + _SETUP_HELP) from exc
    try:
        if settings.ee_service_account and settings.ee_private_key_file:
            credentials = ee.ServiceAccountCredentials(settings.ee_service_account, str(settings.ee_private_key_file))
            ee.Initialize(credentials, project=settings.ee_project)
        else:
            ee.Initialize(project=settings.ee_project)
    except Exception as exc:  # ee raises several unrelated exception types
        raise EarthEngineUnavailable(f"Earth Engine initialisation failed ({exc}). " + _SETUP_HELP) from exc
    _ee = ee
    return ee


def _mask_clouds(ee, image):
    scl = image.select("SCL")
    bad = ee.Image(0)
    for code in _SCL_MASKED:
        bad = bad.Or(scl.eq(code))
    return image.updateMask(bad.Not())


def _composite(ee, settings: Settings, region, year: int, months: tuple[int, int], prefix: str):
    """Median of cloud-masked Sentinel-2 L2A scenes in a season, plus the per-pixel clear-observation count."""
    start = ee.Date.fromYMD(year, months[0], 1)
    end = ee.Date.fromYMD(year, months[1], 1).advance(1, "month")
    scenes = (
        ee.ImageCollection(settings.s2_asset).filterBounds(region).filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", settings.max_cloud_percent))
        .map(lambda img: _mask_clouds(ee, img))
    )
    median = (scenes.select(list(S2_BANDS)).median().unmask(0).toInt16()
              .rename([f"{prefix}_{b}" for b in S2_BANDS]))
    count = scenes.select("B4").count().unmask(0).toInt16().rename(f"n_{prefix}")
    return median.addBands(count)


def build_chip_image(settings: Settings, request: ChipRequest, wgs84_bounds: tuple[float, float, float, float]):
    """Image with exactly the bands in CHIP_BANDS: two composites + Hansen + WorldCover."""
    ee = initialize(settings)
    region = ee.Geometry.Rectangle(list(wgs84_bounds))
    before = _composite(ee, settings, region, request.before_year, request.season_months, "before")
    after = _composite(ee, settings, region, request.after_year, request.season_months, "after")
    hansen = ee.Image(settings.hansen_asset).select(["treecover2000", "lossyear"]).unmask(0).toInt16()
    landcover = ee.ImageCollection(settings.worldcover_asset).mosaic().select("Map").rename("landcover").unmask(0).toInt16()
    return before.addBands(after).addBands(hansen).addBands(landcover).select(list(CHIP_BANDS))


def download_tile(settings: Settings, image, tile: Tile, epsg: int, retries: int = 3) -> bytes:
    """Download one tile as GeoTIFF bytes on the exact 10 m UTM grid of the request."""
    ee = initialize(settings)
    xmin, ymin, xmax, ymax = tile.bounds
    region = ee.Geometry.Rectangle([xmin, ymin, xmax, ymax], proj=f"EPSG:{epsg}", geodesic=False)
    params = {
        "region": region, "crs": f"EPSG:{epsg}", "format": "GEO_TIFF",
        "crs_transform": [PIXEL_SIZE_M, 0, tile.xmin, 0, -PIXEL_SIZE_M, tile.ymax],
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            url = image.getDownloadURL(params)
            response = httpx.get(url, timeout=300, follow_redirects=True)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            last_error = exc
            log.warning("tile download attempt %d/%d failed: %s", attempt, retries, exc)
            time.sleep(2 * attempt)
    raise EarthEngineUnavailable(f"Tile download failed after {retries} attempts: {last_error}")
