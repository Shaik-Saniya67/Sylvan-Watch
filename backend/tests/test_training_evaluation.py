"""Train -> evaluate path on SYNTHETIC chips (checks code paths, protocol and JSON output, not real accuracy)."""
import json

import pytest
from pyproj import Transformer

from sylvan.config import Settings
from sylvan.ml.dataset import Site, load_sites, load_split
from sylvan.ml.evaluation import evaluate_all
from sylvan.ml.training_classical import train_classical
from tests.conftest import build_pair, pair_to_chip

SITES = [
    Site("s_train", (0, 0, 1, 1), "train", (1, 4), 2019, 2023),
    Site("s_val", (0, 0, 1, 1), "val", (1, 4), 2019, 2023),
    Site("s_test_a", (0, 0, 1, 1), "test", (1, 4), 2019, 2023),
    Site("s_test_b", (0, 0, 1, 1), "test", (1, 4), 2019, 2023),
]
SIZES = {"s_train": 160, "s_val": 128, "s_test_a": 192, "s_test_b": 96}


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(storage_dir=tmp_path)
    for site in SITES:
        pair_to_chip(s.chips_dir / site.name / f"{site.name}_r0_c0.tif", build_pair(SIZES[site.name]))
    return s


def test_sites_config_rejects_bad_split(tmp_path):
    bad = tmp_path / "sites.json"
    bad.write_text(json.dumps({"sites": [{"name": "x", "bbox": [0, 0, 1, 1], "split": "dev", "season_months": [1, 4], "before_year": 2019, "after_year": 2023}]}))
    with pytest.raises(ValueError, match="invalid split"):
        load_sites(bad)


def test_splits_are_site_disjoint(settings):
    names = {split: {p.meta["site"] for p in load_split(settings, SITES, split)} for split in ("train", "val", "test")}
    assert names["train"].isdisjoint(names["val"]) and names["train"].isdisjoint(names["test"]) and names["val"].isdisjoint(names["test"])


def test_train_and_evaluate_end_to_end(settings):
    info = train_classical(settings, load_split(settings, SITES, "train"), seed=7)
    assert info["random_forest"]["positive_pixels"] > 0

    report = evaluate_all(settings, SITES)
    assert set(report["models"]) == {"spectral_baseline", "random_forest"}
    assert report["selected_model"] in report["models"]
    assert "Hansen" in report["label_source"] and report["caveats"]
    for model in report["models"].values():
        assert 0 < model["test"]["f1"] <= 1
        assert set(model["per_site_test"]) == {"s_test_a", "s_test_b"}
        assert model["test"]["support"]["loss_pixels"] > 0
        assert model["independent_reference"] is None            # none supplied => must not be invented
    assert report["models"]["random_forest"]["calibration"]["ece"] is not None
    assert report["models"]["spectral_baseline"]["calibration"] is None   # rule-based: no probabilities
    assert report["splits"]["test"]["tiles"] == 2

    written = json.loads((settings.results_dir / "metrics.json").read_text())   # strict JSON, no NaN
    assert written["selected_model"] == report["selected_model"]


def test_independent_reference_polygons_are_scored_only_inside_polygons(settings, tmp_path):
    train_classical(settings, load_split(settings, SITES, "train"), seed=7)
    pair = build_pair(64)   # only supplies the shared CRS/origin; all chips use the same grid origin
    to_wgs = Transformer.from_crs(pair.crs, 4326, always_xy=True).transform

    def box(rows, cols):
        x0, x1 = pair.transform.c + cols.start * 10, pair.transform.c + cols.stop * 10
        y1, y0 = pair.transform.f - rows.start * 10, pair.transform.f - rows.stop * 10
        ring = [to_wgs(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]
        return {"type": "Polygon", "coordinates": [[list(p) for p in ring]]}

    reference = tmp_path / "ref.geojson"
    reference.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kind": "loss"}, "geometry": box(slice(62, 76), slice(74, 82))},   # inside the cleared block of BOTH test chips
        {"type": "Feature", "properties": {"kind": "stable"}, "geometry": box(slice(0, 12), slice(0, 12))},
    ]}))
    report = evaluate_all(settings, SITES, reference)
    for model in report["models"].values():
        ref = model["independent_reference"]
        assert ref is not None and ref["f1"] > 0.9
        # only pixels inside the polygons are scored (2 test chips x polygon area), never the whole chip
        assert ref["support"] == {"loss_pixels": 2 * 14 * 8, "stable_pixels": 2 * 12 * 12}


def test_evaluate_requires_validation_and_test_chips(tmp_path):
    with pytest.raises(ValueError, match="at least one validation site"):
        evaluate_all(Settings(storage_dir=tmp_path), SITES)
