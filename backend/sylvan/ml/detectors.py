"""Common interface for change detectors."""
from typing import Protocol

import numpy as np

from sylvan.ml.pair import Pair


class ChangeDetector(Protocol):
    """Every detector maps a Pair to a per-pixel loss score in [0, 1].

    `calibrated_probability` is False for rule-based detectors, whose output is a hard 0/1 mask.
    """

    name: str
    calibrated_probability: bool

    def predict_score(self, pair: Pair) -> np.ndarray: ...
