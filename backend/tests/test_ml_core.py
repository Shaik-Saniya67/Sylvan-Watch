import numpy as np
import pytest

from sylvan.constants import CHIP_BANDS
from sylvan.data.chips import decode_download, write_chip
from sylvan.ml.baseline import SpectralBaseline
from sylvan.ml.features import FEATURE_COUNT, pixel_features
from sylvan.ml.indices import ndvi
from sylvan.ml.labels import hansen_labels, pair_labels
from sylvan.ml.metrics import CalibrationAccumulator, Confusion, bootstrap_f1, confusion, scores
from sylvan.ml.pair import read_chip
from sylvan.ml.random_forest import RandomForestDetector, sample_training_pixels
from tests.conftest import CLEARED


def test_ndvi_known_value():
    bands = np.zeros((6, 1, 1), np.float32)
    bands[3], bands[2] = 0.5, 0.1   # NIR, Red
    assert ndvi(bands)[0, 0] == pytest.approx(0.4 / 0.6, abs=1e-4)


def test_hansen_label_window_and_domain():
    treecover = np.array([[80, 80, 80, 80, 10]], np.uint8)
    lossyear = np.array([[0, 18, 21, 24, 21]], np.uint8)     # 2018 loss, 2021 loss, 2024 loss
    loss, forest = hansen_labels(treecover, lossyear, before_year=2019, after_year=2023, tree_threshold=30)
    assert forest.tolist() == [[True, False, True, True, False]]   # lost in 2018 => not forest in 2019; 10% cover => not forest
    assert loss.tolist() == [[False, False, True, False, False]]   # 2024 loss is after the window


def test_pair_labels_respect_cloud_mask(pair):
    pair.valid[:, :30] = False
    loss, domain = pair_labels(pair, 30)
    assert not loss[:, :30].any() and not domain[:, :30].any()
    assert loss.sum() == (CLEARED[0].stop - CLEARED[0].start) * (CLEARED[1].stop - 30)


def test_features_shape_and_change_sign(pair):
    feats = pixel_features(pair.before, pair.after)
    assert feats.shape == (64, 64, FEATURE_COUNT)
    d_nbr = feats[..., -2]    # NBR difference channel (before - after)
    assert d_nbr[CLEARED].mean() > 0.3 > abs(d_nbr[:10, :10].mean())


def test_confusion_and_scores():
    pred = np.array([1, 1, 0, 0, 1], bool)
    target = np.array([1, 0, 0, 1, 1], bool)
    c = confusion(pred, target, np.ones(5, bool))
    assert (c.tp, c.fp, c.fn, c.tn) == (2, 1, 1, 1)
    s = scores(c)
    assert s["precision"] == pytest.approx(2 / 3) and s["recall"] == pytest.approx(2 / 3)
    assert s["f1"] == pytest.approx(2 / 3) and s["iou"] == pytest.approx(0.5)
    assert s["confusion_matrix"] == [[1, 1], [1, 2]]


def test_confusion_ignores_pixels_outside_domain():
    domain = np.array([1, 1, 0, 0], bool)
    c = confusion(np.array([1, 0, 1, 1], bool), np.array([1, 0, 0, 0], bool), domain)
    assert (c.tp, c.fp, c.fn, c.tn) == (1, 0, 0, 1)


def test_bootstrap_interval_contains_point_estimate():
    tiles = [Confusion(tp=8, fp=2, fn=2, tn=88), Confusion(tp=5, fp=5, fn=3, tn=87), Confusion(tp=9, fp=1, fn=1, tn=89)]
    lo, hi = bootstrap_f1(tiles)
    pooled = scores(sum(tiles, Confusion()))["f1"]
    assert lo <= pooled <= hi


def test_calibration_perfect_and_overconfident():
    acc = CalibrationAccumulator()
    domain = np.ones(1000, bool)
    target = np.zeros(1000, bool)
    target[:500] = True
    acc.update(np.full(1000, 0.5), target, domain)
    assert acc.result()["ece"] == pytest.approx(0.0, abs=1e-9)
    bad = CalibrationAccumulator()
    bad.update(np.full(1000, 0.95), target, domain)
    assert bad.result()["ece"] == pytest.approx(0.45, abs=0.01)


def test_baseline_fit_finds_cleared_block(pair):
    target, domain = pair_labels(pair, 30)
    baseline = SpectralBaseline().fit([pair], [target], [domain])
    c = confusion(baseline.predict_score(pair) > 0.5, target, domain)
    assert scores(c)["f1"] > 0.95


def test_random_forest_learns_and_predicts_full_tile(pair):
    target, domain = pair_labels(pair, 30)
    x, y = sample_training_pixels([pair], [target], [domain], seed=1)
    assert y.sum() == target.sum() and len(y) > y.sum()
    forest = RandomForestDetector().fit(x, y, seed=1)
    score = forest.predict_score(pair)
    assert score.shape == pair.shape and score[CLEARED].mean() > 0.9 and score[:10, :10].mean() < 0.1


def test_rf_refuses_to_train_without_positives(pair):
    pair.lossyear[:] = 0
    target, domain = pair_labels(pair, 30)
    with pytest.raises(ValueError, match="no loss pixels"):
        sample_training_pixels([pair], [target], [domain], seed=0)


def test_chip_roundtrip(tmp_path, pair):
    from rasterio.crs import CRS
    from rasterio.transform import Affine
    data = np.zeros((len(CHIP_BANDS), 32, 32), np.int16)
    data[CHIP_BANDS.index("n_before")] = 3
    data[CHIP_BANDS.index("n_after")] = 2
    data[CHIP_BANDS.index("before_B8")] = 4000
    data[CHIP_BANDS.index("treecover2000")] = 77
    path = tmp_path / "x.tif"
    write_chip(path, data, Affine(10, 0, 500000, 0, -10, 1000000), CRS.from_epsg(32644),
               {"before_year": "2019", "after_year": "2023"})
    restored = read_chip(path)
    assert restored.before[3].mean() == pytest.approx(0.4) and restored.valid.all()
    assert restored.treecover.max() == 77 and restored.meta["before_year"] == "2019"
    # the same bytes decode identically through the Earth Engine download path
    decoded, transform, crs = decode_download(path.read_bytes())
    assert decoded.shape == data.shape and crs.to_epsg() == 32644 and transform.a == 10
