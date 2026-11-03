"""Siamese U-Net tests; skipped automatically when PyTorch is not installed."""
import numpy as np
import pytest

try:
    import torch
except Exception as exc:  # ImportError, or a broken CUDA installation
    pytest.skip(f"PyTorch unavailable: {exc}", allow_module_level=True)

from sylvan.config import Settings
from sylvan.ml.labels import pair_labels
from sylvan.ml.losses import masked_bce_dice
from sylvan.ml.siamese_detector import SiameseDetector
from sylvan.ml.siamese_unet import SiameseUNet
from sylvan.ml.training_siamese import train_siamese
from tests.conftest import build_pair


def test_forward_shape_and_shared_weights():
    model = SiameseUNet(base=8, depth=3)
    x = torch.randn(2, 6, 32, 32)
    assert model(x, x).shape == (2, 1, 32, 32)
    # Identical before/after => zero feature difference at every scale => output ignores image content.
    model.eval()
    y = torch.randn_like(x)
    assert torch.allclose(model(x, x), model(y, y), atol=1e-5)



def test_loss_is_finite_and_masks_outside_domain():
    logits = torch.zeros(1, 1, 8, 8)
    target = torch.zeros(1, 1, 8, 8)
    target[..., :2] = 1
    full = masked_bce_dice(logits, target, torch.ones_like(target), pos_weight=5.0)
    none_in_domain = masked_bce_dice(logits, target, torch.zeros_like(target), pos_weight=5.0)
    assert torch.isfinite(full) and torch.isfinite(none_in_domain)
    assert full > none_in_domain


def test_detector_handles_non_multiple_of_16_and_masks_invalid(pair):
    detector = SiameseDetector(SiameseUNet(base=8, depth=3), np.zeros(6), np.ones(6))
    pair.valid[:5] = False
    score = detector.predict_score(pair)
    assert score.shape == pair.shape and score.dtype == np.float32
    assert 0 <= score.min() and score.max() <= 1 and (score[:5] == 0).all()


def test_training_runs_saves_checkpoint_and_reduces_loss(tmp_path):
    settings = Settings(storage_dir=tmp_path)
    pair = build_pair(160)
    info = train_siamese(settings, [pair], [pair], seed=3, epochs=4, steps_per_epoch=12, batch_size=4)
    assert len(info["history"]) >= 2
    assert info["history"][-1]["train_loss"] < info["history"][0]["train_loss"]
    detector = SiameseDetector.load(settings.models_dir / "siamese_unet.pt")
    target, domain = pair_labels(pair, 30)
    assert detector.predict_score(pair).shape == target.shape
