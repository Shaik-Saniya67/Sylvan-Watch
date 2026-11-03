"""Pipeline wiring test.

Earth Engine cannot be called in CI, so `fetch_chips` is replaced by a stub that cuts a SYNTHETIC world
into tiles and writes real chip GeoTIFFs. Everything after the download (chip reading, Hansen domain,
detector inference, tile stitching, polygonisation, area, previews, result document, report) runs
unmodified. This checks the code paths; it says nothing about accuracy on real imagery.
"""
import json

import numpy as np
import pytest

from sylvan.config import Settings
from sylvan.constants import CHIP_BANDS, REFLECTANCE_SCALE
from sylvan.data.chips import provenance_tags, write_chip
from sylvan.geo.aoi import BBox
from sylvan.geo.tiling import grid_for_bbox
from sylvan.ml.baseline import SpectralBaseline
from sylvan.ml.labels import pair_labels
from sylvan.pipeline import inference
from sylvan.pipeline.inference import DetectionRequest, run_detection
from sylvan.pipeline.reports import build_markdown_report, load_run_documents
from tests.conftest import build_pair

BBOX = BBox(79.20, 13.60, 79.32, 13.64)   # ~13 x 4.4 km -> 3 tiles wide, so the clearing crosses tile borders


@pytest.fixture
def stubbed_world(monkeypatch, tmp_path):
    settings = Settings(storage_dir=tmp_path)
    settings.models_dir.mkdir(parents=True)
    train_pair = build_pair(64)
    target, domain = pair_labels(train_pair, 30)
    SpectralBaseline().fit([train_pair], [target], [domain]).save(settings.models_dir / "spectral_baseline.json")

    grid = grid_for_bbox(BBOX)
    world = build_pair(max(grid.height, grid.width))

    def fake_fetch(settings, bbox, request, out_dir, prefix, extra_tags=None, on_tile=None, skip_small=False):
        out = []
        for i, tile in enumerate(grid.tiles(), start=1):
            win = (slice(tile.row_off, tile.row_off + tile.height), slice(tile.col_off, tile.col_off + tile.width))
            data = np.zeros((len(CHIP_BANDS), tile.height, tile.width), np.int16)
            for b, name in enumerate(CHIP_BANDS):
                if name.startswith("before_"):
                    data[b] = world.before[b % 6][win] * REFLECTANCE_SCALE
                elif name.startswith("after_"):
                    data[b] = world.after[b % 6 if b < 12 else 0][win] * REFLECTANCE_SCALE
            data[CHIP_BANDS.index("n_before")] = data[CHIP_BANDS.index("n_after")] = 4
            data[CHIP_BANDS.index("treecover2000")] = world.treecover[win]
            data[CHIP_BANDS.index("lossyear")] = world.lossyear[win]
            data[CHIP_BANDS.index("landcover")] = 10
            path = out_dir / f"{prefix}_r{tile.row_off}_c{tile.col_off}.tif"
            write_chip(path, data, tile.transform, __import__("rasterio").crs.CRS.from_epsg(grid.epsg),
                       provenance_tags(settings, request, extra_tags))
            out.append((tile, path))
            on_tile and on_tile(i, len(grid.tiles()))
        return out

    monkeypatch.setattr(inference, "fetch_chips", fake_fetch)
    monkeypatch.setattr(inference.gee_client, "initialize", lambda s: None)
    return settings, grid, world


def test_full_pipeline_stitches_tiles_and_measures_area(stubbed_world, tmp_path):
    settings, grid, world = stubbed_world
    assert len(grid.tiles()) >= 3
    stages = []
    request = DetectionRequest(BBOX, 2019, 2023, (1, 4), model="spectral_baseline")
    result = run_detection(request, settings, tmp_path / "run", lambda stage, p: stages.append((stage, p)))

    # real progress stages, monotonic
    assert stages[0][0] == "loading_model" and stages[-1] == ("done", 1.0)
    assert [p for _, p in stages] == sorted(p for _, p in stages)

    # the single clearing spans several tiles but must come out as ONE polygon with the exact area
    expected_px = int(((world.lossyear[:grid.height, :grid.width]) > 0).sum())
    assert result["summary"]["detections"] == 1
    assert result["summary"]["loss_area_ha"] == pytest.approx(expected_px * 0.01, rel=0.02)
    assert result["data_quality"]["cloud_free_coverage_percent"] == 100.0
    assert result["model"]["name"] == "spectral_baseline" and result["model"]["evaluated"] is False

    run_dir = tmp_path / "run"
    for name in ("before.png", "after.png", "change.png", "detections.geojson", "result.json"):
        assert (run_dir / name).stat().st_size > 0
    doc, detections = load_run_documents(run_dir)
    props = detections["features"][0]["properties"]
    assert props["confidence"] is None and props["landcover"] == "Tree cover"
    assert 79.2 < props["lon"] < 79.32 and 13.6 < props["lat"] < 13.64
    corners = doc["grid"]["corners_lonlat"]
    assert corners[0][0] == pytest.approx(79.20, abs=0.01) and corners[0][1] == pytest.approx(13.64, abs=0.01)

    report = build_markdown_report("t1", doc, detections)
    assert "No evaluation was recorded" in report and "Limitations" in report and "n/a (rule-based)" in report
    json.loads((run_dir / "result.json").read_text())   # valid JSON on disk


def test_missing_model_fails_before_any_download(stubbed_world, tmp_path, monkeypatch):
    settings, *_ = stubbed_world
    called = []
    monkeypatch.setattr(inference, "fetch_chips", lambda *a, **k: called.append(1))
    from sylvan.ml.registry import ModelUnavailable
    with pytest.raises(ModelUnavailable):
        run_detection(DetectionRequest(BBOX, 2019, 2023, (1, 4), model="random_forest"), settings, tmp_path / "r", lambda *_: None)
    assert called == []
