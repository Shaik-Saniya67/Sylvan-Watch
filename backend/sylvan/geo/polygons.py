"""Convert a binary change mask into georeferenced detection polygons."""
import geopandas as gpd
import numpy as np
from rasterio.crs import CRS
from rasterio.features import shapes
from rasterio.transform import Affine
from scipy import ndimage
from shapely.geometry import shape

from sylvan.constants import WORLDCOVER_CLASSES
from sylvan.geo.area import pixel_area_ha

_EIGHT_CONNECTED = np.ones((3, 3), dtype=int)


def mask_to_detections(
    mask: np.ndarray,
    probability: np.ndarray | None,
    landcover: np.ndarray | None,
    transform: Affine,
    crs: CRS,
    min_area_ha: float = 0.5,
) -> gpd.GeoDataFrame:
    """One polygon per 8-connected loss patch, with area, mean confidence and land-cover context.

    `probability` may be None for rule-based detectors, in which case confidence is NaN.
    """
    ha_per_pixel = pixel_area_ha(transform, crs)
    labels, _ = ndimage.label(mask.astype(bool), structure=_EIGHT_CONNECTED)
    rows = []
    for idx, window in enumerate(ndimage.find_objects(labels), start=1):
        patch = labels[window] == idx
        area_ha = float(patch.sum()) * ha_per_pixel
        if area_ha < min_area_ha:
            continue
        sub_transform = transform @ Affine.translation(window[1].start, window[0].start)
        geom = next(
            shape(g) for g, v in shapes(patch.astype(np.uint8), mask=patch, transform=sub_transform, connectivity=8)
            if v == 1
        )
        confidence = float(probability[window][patch].mean()) if probability is not None else float("nan")
        rows.append({
            "geometry": geom,
            "area_ha": round(area_ha, 3),
            "confidence": confidence,
            "landcover": _dominant_landcover(landcover[window][patch]) if landcover is not None else None,
        })
    if not rows:
        return gpd.GeoDataFrame(columns=["area_ha", "confidence", "landcover", "geometry"], geometry="geometry", crs=crs.to_wkt())
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs.to_wkt())


def _dominant_landcover(values: np.ndarray) -> str:
    code = int(np.bincount(values.astype(np.int64).ravel()).argmax())
    return WORLDCOVER_CLASSES.get(code, f"Class {code}")


def to_wgs84_geojson(detections: gpd.GeoDataFrame) -> dict:
    """GeoJSON FeatureCollection in lon/lat; each feature carries its centroid lon/lat."""
    if detections.empty:
        return {"type": "FeatureCollection", "features": []}
    centroids = gpd.GeoSeries(detections.geometry.centroid, crs=detections.crs).to_crs(4326)
    wgs = detections.to_crs(4326).copy()
    wgs["lon"] = centroids.x.round(6).to_numpy()
    wgs["lat"] = centroids.y.round(6).to_numpy()
    wgs = wgs.sort_values("area_ha", ascending=False).reset_index(drop=True)
    wgs["id"] = wgs.index + 1
    collection = wgs.to_geo_dict()
    for feature in collection["features"]:
        conf = feature["properties"]["confidence"]
        # JSON has no NaN: rule-based detectors report confidence as null.
        feature["properties"]["confidence"] = None if conf is None or conf != conf else round(conf, 4)
    return collection
