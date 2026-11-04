"""End-to-end detection for a user-selected area: fetch -> predict -> polygonise -> save."""
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rasterio.crs import CRS
from rasterio.features import rasterize

from sylvan.config import Settings
from sylvan.constants import WORLDCOVER_CLASSES
from sylvan.data import gee_client
from sylvan.data.chips import fetch_chips
from sylvan.data.gee_client import ChipRequest
from sylvan.geo.aoi import BBox
from sylvan.geo.area import pixel_area_ha
from sylvan.geo.polygons import mask_to_detections, to_wgs84_geojson
from sylvan.geo.tiling import grid_for_bbox
from sylvan.ml.labels import hansen_labels
from sylvan.ml.pair import read_chip
from sylvan.ml.registry import load_detector, load_metrics, resolve_model_name
from sylvan.pipeline.render import change_overlay_png, true_color_png, wgs84_corners

Progress = Callable[[str, float], None]


@dataclass(frozen=True)
class DetectionRequest:
    bbox: BBox
    before_year: int
    after_year: int
    season_months: tuple[int, int]
    model: str = "best"


def _model_info(settings: Settings, name: str) -> tuple[float, dict]:
    """Decision threshold and evaluation summary recorded for `name` (defaults if never evaluated)."""
    metrics = load_metrics(settings)
    entry = (metrics or {}).get("models", {}).get(name)
    if not entry:
        return 0.5, {"evaluated": False, "note": "No evaluation recorded; default threshold 0.5 used."}
    return entry["threshold"], {
        "evaluated": True, "threshold": entry["threshold"],
        "test_f1": entry["test"]["f1"], "test_precision": entry["test"]["precision"],
        "test_recall": entry["test"]["recall"], "test_iou": entry["test"]["iou"],
        "metrics_generated_at": metrics["generated_at"],
    }


def run_detection(request: DetectionRequest, settings: Settings, run_dir: Path, progress: Progress) -> dict:
    """Run the full pipeline and write all artefacts into `run_dir`. Returns the result document."""
    started = time.time()
    run_dir.mkdir(parents=True, exist_ok=True)

    progress("loading_model", 0.02)
    model_name = resolve_model_name(settings, request.model)
    detector = load_detector(settings, model_name)           # fail before any download
    threshold, model_eval = _model_info(settings, model_name)

    progress("authenticating", 0.05)
    gee_client.initialize(settings)

    chip_request = ChipRequest(request.before_year, request.after_year, request.season_months)
    grid = grid_for_bbox(request.bbox)
    tiles = fetch_chips(
        settings, request.bbox, chip_request, run_dir / "chips", "aoi",
        on_tile=lambda i, n: progress("fetching_imagery", 0.05 + 0.6 * i / n),
    )

    progress("predicting", 0.67)
    height, width = grid.height, grid.width
    score = np.zeros((height, width), np.float32)
    domain = np.zeros((height, width), bool)
    valid = np.zeros((height, width), bool)
    landcover = np.zeros((height, width), np.uint8)
    # Preview images only need B2/B3/B4. Keep those three bands instead of
    # retaining all six float32 bands for both dates across the full AOI.
    # Model inference still receives the complete Pair for every tile.
    before_rgb = np.zeros((3, height, width), np.float32)
    after_rgb = np.zeros_like(before_rgb)
    for tile, path in tiles:
        pair = read_chip(path)
        window = (slice(tile.row_off, tile.row_off + tile.height), slice(tile.col_off, tile.col_off + tile.width))
        _, forest = hansen_labels(pair.treecover, pair.lossyear, request.before_year, request.after_year,
                                  settings.tree_cover_threshold)
        score[window] = detector.predict_score(pair)
        domain[window], valid[window], landcover[window] = forest & pair.valid, pair.valid, pair.landcover
        before_rgb[(slice(None), *window)], after_rgb[(slice(None), *window)] = pair.before[:3], pair.after[:3]
        crs = pair.crs

    progress("vectorising", 0.85)
    mask = (score >= threshold) & domain
    detections = mask_to_detections(
        mask, score if detector.calibrated_probability else None, landcover, grid.transform,
        CRS.from_epsg(grid.epsg), settings.min_detection_ha,
    )
    geojson = to_wgs84_geojson(detections)

    progress("writing_outputs", 0.93)
    kept = np.zeros_like(mask)
    if len(detections):
        kept = rasterize(((g, 1) for g in detections.geometry), out_shape=mask.shape, transform=grid.transform,
                         fill=0, dtype="uint8", all_touched=False).astype(bool) & mask
    true_color_png(before_rgb, valid, run_dir / "before.png")
    true_color_png(after_rgb, valid, run_dir / "after.png")
    change_overlay_png(kept, score, run_dir / "change.png")
    (run_dir / "detections.geojson").write_text(json.dumps(geojson))

    ha_px = pixel_area_ha(grid.transform, crs)
    total_px = height * width
    loss_by_class = {}
    for code in np.unique(landcover[kept]):
        loss_by_class[WORLDCOVER_CLASSES.get(int(code), f"Class {int(code)}")] = round(float((kept & (landcover == code)).sum()) * ha_px, 2)

    result = {
        "request": {
            "bbox": [request.bbox.west, request.bbox.south, request.bbox.east, request.bbox.north],
            "before_year": request.before_year, "after_year": request.after_year,
            "season_months": list(request.season_months), "model_requested": request.model,
        },
        "model": {"name": model_name, "calibrated_probability": detector.calibrated_probability, **model_eval},
        "datasets": {"sentinel2": settings.s2_asset, "hansen": settings.hansen_asset,
                     "worldcover": settings.worldcover_asset,
                     "tree_cover_threshold_percent": settings.tree_cover_threshold},
        "grid": {"epsg": grid.epsg, "height": height, "width": width, "pixel_size_m": 10,
                 "corners_lonlat": wgs84_corners(grid)},
        "summary": {
            "detections": int(len(detections)),
            "loss_area_ha": round(float(kept.sum()) * ha_px, 2),
            "forest_area_ha": round(float(domain.sum()) * ha_px, 2),
            "loss_percent_of_forest": round(100 * float(kept.sum()) / max(int(domain.sum()), 1), 3),
            "loss_area_by_landcover_ha": loss_by_class,
        },
        "data_quality": {
            "cloud_free_coverage_percent": round(100 * float(valid.sum()) / total_px, 2),
            "min_detection_ha": settings.min_detection_ha,
            "tiles": len(tiles),
        },
        "notes": [
            "Forest = Hansen canopy >= threshold in 2000 and not lost before the 'before' year; only these pixels are scanned.",
            "Land-cover class is ESA WorldCover 2021 and reflects the state after clearing, so 'Cropland' on a detection can mean converted forest.",
            "Detections show forest-cover loss; imagery cannot establish whether it was legal.",
        ],
        "runtime_seconds": round(time.time() - started, 1),
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    progress("done", 1.0)
    return result
