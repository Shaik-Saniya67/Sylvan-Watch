"""Approach B: Memory-efficient Random Forest on multispectral features."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from sylvan.ml.features import pixel_features
from sylvan.ml.pair import Pair


NEGATIVES_PER_POSITIVE = 2
MAX_POSITIVES = 75_000


def _allocate_quotas(counts: list[int], total: int) -> list[int]:
    """Distribute a sample budget proportionally across chips."""
    available = sum(counts)

    if available == 0 or total == 0:
        return [0] * len(counts)

    total = min(total, available)
    exact = [count * total / available for count in counts]
    quotas = [int(value) for value in exact]

    remainder = total - sum(quotas)
    order = sorted(
        range(len(counts)),
        key=lambda i: exact[i] - quotas[i],
        reverse=True,
    )

    for i in order[:remainder]:
        quotas[i] += 1

    return quotas


def _sample_indices(
    indices: np.ndarray,
    quota: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Select up to quota indices without replacement."""
    if quota <= 0:
        return np.empty(0, dtype=np.int64)

    if quota >= len(indices):
        return indices

    return rng.choice(indices, size=quota, replace=False)


def sample_training_pixels(
    pairs: list[Pair],
    targets: list[np.ndarray],
    domains: list[np.ndarray],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample training pixels without retaining full feature arrays for all chips."""
    if not pairs:
        raise ValueError("No training chips were provided.")

    if not (len(pairs) == len(targets) == len(domains)):
        raise ValueError("Pairs, targets and domains must have equal lengths.")

    rng = np.random.default_rng(seed)

    positive_counts = []
    negative_counts = []

    # First pass: count eligible pixels without creating feature arrays.
    for pair, target, domain in zip(pairs, targets, domains, strict=True):
        if target.shape != pair.shape or domain.shape != pair.shape:
            raise ValueError(
                "Target and domain shapes must match the chip dimensions."
            )

        positive_counts.append(int(np.count_nonzero(target & domain)))
        negative_counts.append(int(np.count_nonzero((~target) & domain)))

    total_positive = sum(positive_counts)
    total_negative = sum(negative_counts)

    if total_positive == 0:
        raise ValueError("Training chips contain no loss pixels.")

    if total_negative == 0:
        raise ValueError("Training chips contain no valid negative pixels.")

    positive_budget = min(total_positive, MAX_POSITIVES)
    negative_budget = min(
        total_negative,
        positive_budget * NEGATIVES_PER_POSITIVE,
    )

    positive_quotas = _allocate_quotas(positive_counts, positive_budget)
    negative_quotas = _allocate_quotas(negative_counts, negative_budget)

    positive_parts = []
    negative_parts = []

    # Second pass: build features for one chip at a time.
    for pair, target, domain, pos_quota, neg_quota in zip(
        pairs,
        targets,
        domains,
        positive_quotas,
        negative_quotas,
        strict=True,
    ):
        if pos_quota == 0 and neg_quota == 0:
            continue

        features = pixel_features(pair.before, pair.after)
        flat_features = features.reshape(-1, features.shape[-1])

        positive_indices = np.flatnonzero((target & domain).ravel())
        negative_indices = np.flatnonzero(((~target) & domain).ravel())

        selected_positive = _sample_indices(
            positive_indices, pos_quota, rng
        )
        selected_negative = _sample_indices(
            negative_indices, neg_quota, rng
        )

        if len(selected_positive):
            positive_parts.append(flat_features[selected_positive].copy())

        if len(selected_negative):
            negative_parts.append(flat_features[selected_negative].copy())

        del features, flat_features

    positive_features = np.concatenate(positive_parts, axis=0)
    negative_features = np.concatenate(negative_parts, axis=0)

    x = np.concatenate(
        [positive_features, negative_features], axis=0
    ).astype(np.float32, copy=False)

    y = np.concatenate(
        [
            np.ones(len(positive_features), dtype=np.uint8),
            np.zeros(len(negative_features), dtype=np.uint8),
        ]
    )

    # Shuffle the final sample.
    order = rng.permutation(len(y))
    return x[order], y[order]


class RandomForestDetector:
    name = "random_forest"
    calibrated_probability = True

    def __init__(
        self,
        model: RandomForestClassifier | None = None,
        name: str = "random_forest",
    ) -> None:
        self.model = model
        self.name = name

    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        seed: int,
        class_weight: str | dict | None = "balanced_subsample",
        n_estimators: int = 100,
        min_samples_leaf: int = 5,
    ) -> "RandomForestDetector":
        """Train the Random Forest with configurable hyperparameters."""
        if len(x) == 0 or len(np.unique(y)) < 2:
            raise ValueError("Random Forest training requires both classes.")

        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            min_samples_leaf=min_samples_leaf,
            class_weight=class_weight,
            n_jobs=2,
            random_state=seed,
        )

        self.model.fit(x, y)
        return self

    def predict_score(self, pair: Pair) -> np.ndarray:
        """Predict in batches to limit peak memory usage."""
        if self.model is None:
            raise RuntimeError("Random Forest has not been trained.")

        out = np.zeros(pair.shape, dtype=np.float32)
        valid_indices = np.flatnonzero(pair.valid.ravel())

        if len(valid_indices) == 0:
            return out

        features = pixel_features(pair.before, pair.after)
        flat_features = features.reshape(-1, features.shape[-1])

        batch_size = 10_000
        flat_out = out.ravel()

        for start in range(0, len(valid_indices), batch_size):
            batch_indices = valid_indices[start:start + batch_size]
            batch_features = flat_features[batch_indices]

            flat_out[batch_indices] = self.model.predict_proba(
                batch_features
            )[:, 1]

        return out

    def save(self, path: Path) -> None:
        """Save the trained model."""
        if self.model is None:
            raise RuntimeError("Cannot save an untrained Random Forest.")

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path, compress=3)

    @classmethod
    def load(cls, path: Path) -> "RandomForestDetector":
        """Load a saved Random Forest."""
        return cls(joblib.load(path))