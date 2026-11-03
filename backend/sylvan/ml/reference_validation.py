"""Validation against independently digitised reference polygons (e.g. traced on very-high-resolution imagery).

GeoJSON features need a property `kind`: "loss" (verified forest loss) or "stable" (verified intact forest).
Only pixels inside these polygons are scored, so unlabelled areas never count as errors.
"""
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from rasterio.features import rasterize
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

from sylvan.ml.metrics import Confusion, confusion
from sylvan.ml.pair import Pair


def load_reference(path: Path) -> list[tuple[object, str]]:
    features = json.loads(path.read_text())["features"]
    out = []
    for feature in features:
        kind = feature.get("properties", {}).get("kind")
        if kind not in ("loss", "stable"):
            raise ValueError("Every reference feature needs properties.kind = 'loss' or 'stable'.")
        out.append((shape(feature["geometry"]), kind))
    return out


def reference_masks(pair: Pair, reference: list[tuple[object, str]]) -> tuple[np.ndarray, np.ndarray]:
    """(loss_mask, scored_mask) rasterised on the chip grid. Polygons are assumed to be in WGS84."""
    to_chip = Transformer.from_crs(4326, pair.crs, always_xy=True).transform
    shapes_by_kind = {"loss": [], "stable": []}
    for geometry, kind in reference:
        shapes_by_kind[kind].append((shapely_transform(to_chip, geometry), 1))

    def burn(items):
        if not items:
            return np.zeros(pair.shape, dtype=bool)
        return rasterize(items, out_shape=pair.shape, transform=pair.transform, fill=0, dtype="uint8").astype(bool)

    loss, stable = burn(shapes_by_kind["loss"]), burn(shapes_by_kind["stable"])
    return loss, (loss | stable) & pair.valid


def score_against_reference(
    pairs: list[Pair], score_maps: list[np.ndarray], threshold: float, reference: list[tuple[object, str]]
) -> Confusion:
    total = Confusion()
    for pair, score in zip(pairs, score_maps, strict=True):
        loss, scored = reference_masks(pair, reference)
        if scored.any():
            total = total + confusion(score >= threshold, loss, scored)
    return total
