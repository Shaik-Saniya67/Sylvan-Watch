import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import Affine

from sylvan.geo.aoi import BBox, InvalidAOI, utm_epsg
from sylvan.geo.area import mask_area_ha, pixel_area_ha
from sylvan.geo.polygons import mask_to_detections, to_wgs84_geojson
from sylvan.geo.tiling import grid_for_bbox

UTM44 = CRS.from_epsg(32644)
T10 = Affine(10, 0, 500000, 0, -10, 1000000)


def test_pixel_area_is_hundredth_hectare_at_10m():
    assert pixel_area_ha(T10, UTM44) == pytest.approx(0.01)


def test_pixel_area_rejects_geographic_crs():
    with pytest.raises(ValueError):
        pixel_area_ha(Affine(0.0001, 0, 0, 0, -0.0001, 0), CRS.from_epsg(4326))


def test_mask_area():
    mask = np.zeros((10, 10), bool)
    mask[:5, :4] = True   # 20 px
    assert mask_area_ha(mask, T10, UTM44) == pytest.approx(0.2)


def test_bbox_validation():
    BBox(79.2, 13.5, 79.3, 13.6).validate(15)
    with pytest.raises(InvalidAOI):
        BBox(79.3, 13.5, 79.2, 13.6).validate(15)
    with pytest.raises(InvalidAOI):
        BBox(79.0, 13.0, 79.5, 13.6).validate(15)   # ~54 km wide


def test_utm_zone():
    assert utm_epsg(79.35, 13.68) == 32644
    assert utm_epsg(-63.5, -9.7) == 32720


def test_grid_is_aligned_and_tiles_cover_exactly():
    grid = grid_for_bbox(BBox(79.20, 13.55, 79.30, 13.65))
    assert grid.xmin % 10 == 0 and grid.ymax % 10 == 0
    tiles = grid.tiles(size=512)
    assert sum(t.height * t.width for t in tiles) == grid.height * grid.width
    first = tiles[0]
    assert (first.row_off, first.col_off) == (0, 0)
    assert first.bounds[3] == grid.ymax


def test_detections_area_filter_confidence_and_geojson():
    mask = np.zeros((100, 100), bool)
    mask[10:30, 10:30] = True     # 400 px = 4 ha
    mask[60:62, 60:62] = True     # 4 px = 0.04 ha -> dropped by 0.5 ha filter
    prob = np.where(mask, 0.8, 0.0).astype(np.float32)
    land = np.full(mask.shape, 40, np.uint8)
    gdf = mask_to_detections(mask, prob, land, T10, UTM44, min_area_ha=0.5)
    assert len(gdf) == 1
    row = gdf.iloc[0]
    assert row.area_ha == pytest.approx(4.0)
    assert row.confidence == pytest.approx(0.8)
    assert row.landcover == "Cropland"
    assert gdf.geometry.iloc[0].area == pytest.approx(400 * 100)    # m2

    collection = to_wgs84_geojson(gdf)
    props = collection["features"][0]["properties"]
    # UTM zone 44N: easting ~500 km sits on the 81E central meridian; northing 1,000 km is ~9N
    assert 80.9 < props["lon"] < 81.1 and 8.9 < props["lat"] < 9.2
    assert collection["features"][0]["geometry"]["type"] == "Polygon"


def test_rule_based_confidence_is_null():
    mask = np.zeros((50, 50), bool)
    mask[5:25, 5:25] = True
    collection = to_wgs84_geojson(mask_to_detections(mask, None, None, T10, UTM44))
    assert collection["features"][0]["properties"]["confidence"] is None


def test_empty_mask_gives_empty_collection():
    gdf = mask_to_detections(np.zeros((20, 20), bool), None, None, T10, UTM44)
    assert to_wgs84_geojson(gdf)["features"] == []
