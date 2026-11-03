"""Inference wrapper and checkpoint I/O for the Siamese U-Net."""
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from sylvan.constants import MODEL_DIVISOR
from sylvan.ml.pair import Pair
from sylvan.ml.siamese_unet import SiameseUNet


class SiameseDetector:
    name = "siamese_unet"
    calibrated_probability = True

    def __init__(self, model: SiameseUNet, mean: np.ndarray, std: np.ndarray, device: str = "cpu") -> None:
        self.model = model.to(device).eval()
        self.mean = torch.tensor(mean, dtype=torch.float32, device=device).view(1, -1, 1, 1)
        self.std = torch.tensor(std, dtype=torch.float32, device=device).view(1, -1, 1, 1)
        self.device = device

    def normalize(self, bands: np.ndarray) -> torch.Tensor:
        x = torch.from_numpy(bands).unsqueeze(0).to(self.device)
        return (x - self.mean) / self.std

    @torch.no_grad()
    def predict_score(self, pair: Pair) -> np.ndarray:
        """Per-pixel P(loss). Inputs are reflect-padded to a multiple of 16 and the output cropped back."""
        height, width = pair.shape
        pad_h, pad_w = (-height) % MODEL_DIVISOR, (-width) % MODEL_DIVISOR
        before, after = self.normalize(pair.before), self.normalize(pair.after)
        before, after = (F.pad(t, (0, pad_w, 0, pad_h), mode="reflect") for t in (before, after))
        prob = torch.sigmoid(self.model(before, after))[0, 0, :height, :width].cpu().numpy()
        return np.where(pair.valid, prob, 0.0).astype(np.float32)

    def save(self, path: Path, extra: dict) -> None:
        torch.save({
            "state_dict": self.model.state_dict(),
            "mean": self.mean.flatten().tolist(), "std": self.std.flatten().tolist(),
            **extra,
        }, path)

    @classmethod
    def load(cls, path: Path, device: str = "cpu") -> "SiameseDetector":
        ckpt = torch.load(path, map_location=device, weights_only=True)
        model = SiameseUNet(base=ckpt["base"], depth=ckpt["depth"])
        model.load_state_dict(ckpt["state_dict"])
        return cls(model, np.array(ckpt["mean"]), np.array(ckpt["std"]), device)
