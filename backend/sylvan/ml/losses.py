"""Class-imbalance-aware loss restricted to valid forest pixels."""
import torch
import torch.nn.functional as F


def masked_bce_dice(
    logits: torch.Tensor, target: torch.Tensor, domain: torch.Tensor, pos_weight: float
) -> torch.Tensor:
    """Weighted BCE + soft Dice over `domain` pixels only.

    BCE with `pos_weight` counters the rarity of loss pixels; Dice directly optimises overlap and is
    insensitive to the number of background pixels. Shapes: all (N, 1, H, W).
    """
    weight = torch.tensor(pos_weight, device=logits.device)
    bce = F.binary_cross_entropy_with_logits(logits, target, pos_weight=weight, reduction="none")
    bce = (bce * domain).sum() / domain.sum().clamp(min=1.0)
    prob = torch.sigmoid(logits) * domain
    tgt = target * domain
    dice = 1.0 - (2.0 * (prob * tgt).sum() + 1.0) / (prob.sum() + tgt.sum() + 1.0)
    return bce + dice
