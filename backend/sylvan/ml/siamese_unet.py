"""Approach C: Siamese U-Net for pixel-level change segmentation.

A weight-shared encoder embeds the before and after images. At every scale the decoder receives
the absolute feature difference |f_before - f_after| as its skip connection ("Siam-diff"), so the
network learns what changed rather than what is present.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
    )


class SiameseUNet(nn.Module):
    def __init__(self, in_channels: int = 6, base: int = 16, depth: int = 4) -> None:
        super().__init__()
        channels = [base * 2**i for i in range(depth + 1)]
        self.encoder = nn.ModuleList(
            [_conv_block(in_channels if i == 0 else channels[i - 1], channels[i]) for i in range(depth + 1)]
        )
        self.upsample = nn.ModuleList(
            [nn.ConvTranspose2d(channels[i], channels[i - 1], 2, stride=2) for i in range(depth, 0, -1)]
        )
        self.decoder = nn.ModuleList([_conv_block(channels[i - 1] * 2, channels[i - 1]) for i in range(depth, 0, -1)])
        self.head = nn.Conv2d(channels[0], 1, 1)

    def _encode(self, x: torch.Tensor) -> list[torch.Tensor]:
        features = []
        for i, block in enumerate(self.encoder):
            x = block(x if i == 0 else F.max_pool2d(x, 2))
            features.append(x)
        return features

    def forward(self, before: torch.Tensor, after: torch.Tensor) -> torch.Tensor:
        """Logits of shape (N, 1, H, W); H and W must be divisible by 2**depth."""
        diffs = [torch.abs(a - b) for a, b in zip(self._encode(before), self._encode(after), strict=True)]
        x = diffs[-1]
        for upsample, decode, skip in zip(self.upsample, self.decoder, reversed(diffs[:-1]), strict=True):
            x = decode(torch.cat([upsample(x), skip], dim=1))
        return self.head(x)
