"""Training/evaluation labels derived from Hansen Global Forest Change.

IMPORTANT: Hansen loss is a Landsat-derived *reference product*, not field-verified truth.
Metrics computed against it measure agreement with that product.
"""
import numpy as np

from sylvan.ml.pair import Pair


def hansen_labels(
    treecover: np.ndarray, lossyear: np.ndarray, before_year: int, after_year: int, tree_threshold: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return (loss, forest_at_before).

    forest_at_before: canopy >= threshold in 2000 and not already lost by `before_year`.
    loss: forest_at_before pixels whose Hansen loss year lies in (before_year, after_year].
    """
    first, last = before_year - 2000, after_year - 2000
    forest = (treecover >= tree_threshold) & ((lossyear == 0) | (lossyear > first))
    loss = forest & (lossyear > first) & (lossyear <= last)
    return loss, forest


def pair_labels(pair: Pair, tree_threshold: int) -> tuple[np.ndarray, np.ndarray]:
    """(loss, domain) for a chip. `domain` = forest at the before date AND cloud-free in both periods.

    All metrics and training losses are restricted to the domain, so models are never scored
    on pixels that were not forest or not observed.
    """
    loss, forest = hansen_labels(
        pair.treecover, pair.lossyear,
        int(pair.meta["before_year"]), int(pair.meta["after_year"]), tree_threshold,
    )
    domain = forest & pair.valid
    return loss & domain, domain
