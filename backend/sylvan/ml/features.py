"""Per-pixel feature engineering for the Random Forest and spectral baseline."""

import numpy as np

from sylvan.ml.indices import index_stack


def pixel_features(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """Return 27 features: before, after, band differences, and index differences."""
    idx_before, idx_after = index_stack(before), index_stack(after)

    stack = np.concatenate(
        [before, after, before - after, idx_before, idx_after, idx_before - idx_after],
        axis=0,
    )

    return np.moveaxis(stack, 0, -1).astype(np.float32)


def difference_features(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """Return only 9 temporal-change features: 6 band and 3 index differences."""
    idx_before, idx_after = index_stack(before), index_stack(after)

    stack = np.concatenate(
        [before - after, idx_before - idx_after],
        axis=0,
    )

    return np.moveaxis(stack, 0, -1).astype(np.float32)


FEATURE_COUNT = 27
DIFF_FEATURE_COUNT = 9