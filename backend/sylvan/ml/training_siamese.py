"""Train the Siamese U-Net on training chips; model selection uses validation chips only."""
import logging
import random

import numpy as np
import torch

from sylvan.config import Settings
from sylvan.ml.labels import pair_labels
from sylvan.ml.losses import masked_bce_dice
from sylvan.ml.metrics import confusion, scores
from sylvan.ml.pair import Pair
from sylvan.ml.siamese_detector import SiameseDetector
from sylvan.ml.siamese_unet import SiameseUNet

log = logging.getLogger(__name__)
CROP = 128
BASE_CHANNELS, DEPTH = 16, 4


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _band_statistics(pairs: list[Pair]) -> tuple[np.ndarray, np.ndarray]:
    """Per-band mean/std over valid pixels of both dates in the training set."""
    samples = np.concatenate([np.concatenate([p.before[:, p.valid], p.after[:, p.valid]], axis=1) for p in pairs], axis=1)
    return samples.mean(axis=1), samples.std(axis=1) + 1e-6


def _make_batch(rng, items, batch_size, positive_fraction):
    """Random 128x128 crops with flips/rot90 applied jointly; a fraction is centred on loss pixels."""
    before, after, target, domain = [], [], [], []
    for _ in range(batch_size):
        b, a, t, d, positives = items[rng.integers(len(items))]
        height, width = t.shape
        if len(positives) and rng.random() < positive_fraction:
            r, c = positives[rng.integers(len(positives))]
            top = int(np.clip(r - rng.integers(CROP), 0, height - CROP))
            left = int(np.clip(c - rng.integers(CROP), 0, width - CROP))
        else:
            top, left = int(rng.integers(height - CROP + 1)), int(rng.integers(width - CROP + 1))
        window = (slice(None), slice(top, top + CROP), slice(left, left + CROP))
        crops = [x[window] for x in (b, a)] + [x[window[1:]][None] for x in (t, d)]
        k, flip = int(rng.integers(4)), bool(rng.integers(2))
        crops = [np.rot90(x, k, axes=(1, 2)) for x in crops]
        crops = [x[:, :, ::-1] if flip else x for x in crops]
        for bucket, x in zip((before, after, target, domain), crops, strict=True):
            bucket.append(np.ascontiguousarray(x))
    return [torch.from_numpy(np.stack(x)).float() for x in (before, after, target, domain)]


def train_siamese(
    settings: Settings, train: list[Pair], val: list[Pair], seed: int = 42,
    epochs: int = 40, steps_per_epoch: int = 100, batch_size: int = 16, patience: int = 8,
) -> dict:
    """Fit the model, save the best-on-validation checkpoint, and return the training history."""
    _seed_everything(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    mean, std = _band_statistics(train)
    stats = (mean[:, None, None].astype(np.float32), std[:, None, None].astype(np.float32))

    items, pos_total, neg_total = [], 0, 0
    for pair in train:
        loss, domain = pair_labels(pair, settings.tree_cover_threshold)
        if min(pair.shape) < CROP:
            continue
        rows, cols = np.nonzero(loss)
        keep = np.random.default_rng(seed).permutation(len(rows))[:5000]
        items.append(((pair.before - stats[0]) / stats[1], (pair.after - stats[0]) / stats[1],
                      loss.astype(np.float32), domain.astype(np.float32), np.stack([rows[keep], cols[keep]], 1)))
        pos_total, neg_total = pos_total + int(loss.sum()), neg_total + int((domain & ~loss).sum())
    if pos_total == 0:
        raise ValueError("Training chips contain no loss pixels; cannot train the Siamese U-Net.")
    # sqrt keeps the positive weight moderate; Dice in the loss handles the rest of the imbalance.
    pos_weight = float(np.clip(np.sqrt(neg_total / pos_total), 1.0, 20.0))

    model = SiameseUNet(base=BASE_CHANNELS, depth=DEPTH).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    rng = np.random.default_rng(seed)
    history, best_f1, stale = [], -1.0, 0
    ckpt_path = settings.models_dir / "siamese_unet.pt"
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        model.train()
        running = 0.0
        for _ in range(steps_per_epoch):
            b, a, t, d = (x.to(device) for x in _make_batch(rng, items, batch_size, positive_fraction=0.5))
            optimizer.zero_grad()
            loss = masked_bce_dice(model(b, a), t, d, pos_weight)
            loss.backward()
            optimizer.step()
            running += float(loss)
        scheduler.step()

        detector = SiameseDetector(model, mean, std, device)
        total = None
        for pair in val:
            target, domain = pair_labels(pair, settings.tree_cover_threshold)
            c = confusion(detector.predict_score(pair) >= 0.5, target, domain)
            total = c if total is None else total + c
        val_f1 = scores(total)["f1"] if total else 0.0
        history.append({"epoch": epoch, "train_loss": running / steps_per_epoch, "val_f1": val_f1})
        log.info("epoch %d  train_loss %.4f  val_f1 %.4f", epoch, history[-1]["train_loss"], val_f1)

        if val_f1 > best_f1:
            best_f1, stale = val_f1, 0
            detector.save(ckpt_path, {"base": BASE_CHANNELS, "depth": DEPTH, "epoch": epoch, "val_f1": val_f1, "seed": seed})
        else:
            stale += 1
            if stale >= patience:
                break
    return {"history": history, "best_val_f1": best_f1, "pos_weight": pos_weight, "seed": seed, "device": device}
