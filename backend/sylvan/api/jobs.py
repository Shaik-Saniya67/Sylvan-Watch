"""Background execution and on-disk registry of detection runs."""

import json
import logging
import os
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sylvan.config import Settings
from sylvan.data.gee_client import EarthEngineUnavailable
from sylvan.ml.registry import (
    ModelUnavailable,
    resolve_model_name,
    load_metrics,
)
from sylvan.pipeline.inference import DetectionRequest, run_detection

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)
_lock = threading.Lock()
_submit_lock = threading.Lock()


class RunStore:
    """Each run lives in storage/runs/<id>/."""

    def __init__(self, settings: Settings) -> None:
        self.root = settings.runs_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str):
        return self.root / run_id

    def write_status(self, run_id: str, **fields) -> None:
        with _lock:
            path = self.path(run_id) / "status.json"
            current = json.loads(path.read_text()) if path.exists() else {}
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({**current, **fields, "updated_at": _now()})
            )
            os.replace(tmp, path)

    def status(self, run_id: str):
        path = self.path(run_id) / "status.json"
        return json.loads(path.read_text()) if path.exists() else None

    def list(self) -> list[dict]:
        runs = []

        for status_file in self.root.glob("*/status.json"):
            status = json.loads(status_file.read_text())
            result_file = status_file.parent / "result.json"

            if result_file.exists():
                result = json.loads(result_file.read_text())
                status["summary"] = result["summary"]
                status["request"] = result["request"]
                status["model"] = result["model"]["name"]

            runs.append(status)

        return sorted(
            runs,
            key=lambda s: s["created_at"],
            reverse=True,
        )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _find_cached_run(
    store,
    request,
    model_name,
    metrics_generated_at,
):
    expected_bbox = [
        request.bbox.west,
        request.bbox.south,
        request.bbox.east,
        request.bbox.north,
    ]

    for status_file in store.root.glob("*/status.json"):
        try:
            status = json.loads(status_file.read_text())

            if status.get("state") != "done":
                continue

            result_file = status_file.parent / "result.json"

            if not result_file.exists():
                continue

            result = json.loads(result_file.read_text())
            old_request = result["request"]
            old_model = result["model"]

            if (
                old_request["bbox"] == expected_bbox
                and old_request["before_year"] == request.before_year
                and old_request["after_year"] == request.after_year
                and old_request["season_months"] == list(
                    request.season_months
                )
                and old_model["name"] == model_name
                and old_model.get("metrics_generated_at")
                == metrics_generated_at
            ):
                return status["id"]

        except (OSError, ValueError, KeyError, TypeError):
            continue

    return None


def submit(
    store: RunStore,
    settings: Settings,
    request: DetectionRequest,
) -> str:

    with _submit_lock:
        try:
            model_name = resolve_model_name(settings, request.model)
        except ModelUnavailable:
            model_name = None

        # Reuse a completed run only when the model evaluation
        # timestamp also matches the current evaluation.
        if model_name is not None:
            metrics = load_metrics(settings) or {}
            metrics_generated_at = metrics.get("generated_at")

            if metrics_generated_at:
                cached_id = _find_cached_run(
                    store,
                    request,
                    model_name,
                    metrics_generated_at,
                )

                if cached_id:
                    log.info(
                        "Reusing completed detection run %s",
                        cached_id,
                    )
                    return cached_id

        run_id = uuid.uuid4().hex[:10]

        store.path(run_id).mkdir(parents=True)

        store.write_status(
            run_id,
            id=run_id,
            state="queued",
            stage="queued",
            progress=0.0,
            created_at=_now(),
        )

        def work():
            store.write_status(run_id, state="running")

            try:
                run_detection(
                    request,
                    settings,
                    store.path(run_id),
                    lambda stage, p: store.write_status(
                        run_id,
                        stage=stage,
                        progress=round(p, 3),
                    ),
                )

                store.write_status(run_id, state="done")

            except (
                EarthEngineUnavailable,
                ModelUnavailable,
                ValueError,
            ) as exc:
                log.warning("run %s failed: %s", run_id, exc)
                store.write_status(
                    run_id,
                    state="failed",
                    error=str(exc),
                )

            except Exception as exc:
                log.error(
                    "run %s crashed\n%s",
                    run_id,
                    traceback.format_exc(),
                )
                store.write_status(
                    run_id,
                    state="failed",
                    error=f"Unexpected error: {exc}",
                )

        _executor.submit(work)

        return run_id