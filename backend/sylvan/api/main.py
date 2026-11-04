"""FastAPI application: REST API for detection runs, metrics and reports."""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from sylvan.api.jobs import RunStore, submit
from sylvan.api.schemas import DetectionIn, RunCreated
from sylvan.config import get_settings
from sylvan.geo.aoi import BBox, InvalidAOI
from sylvan.ml.registry import MODEL_NAMES, available_models, load_metrics
from sylvan.pipeline.inference import DetectionRequest
from sylvan.pipeline.reports import (
    build_markdown_report,
    build_pdf_report,
    load_run_documents,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = get_settings()
store = RunStore(settings)

app = FastAPI(
    title="Sylvan Watch API",
    version="0.1.0",
    description="Satellite-based forest-loss detection using Sentinel-2, Hansen GFC and trained models.",
)

app.add_middleware(
    CORSMiddleware,
    # Keep the production Vercel origin explicitly allowed even when the
    # Render environment variable is unset or still contains localhost values.
    allow_origins=list(dict.fromkeys([
        *settings.cors_origins,
        "https://project-mzb0n.vercel.app",
    ])),
    # Vercel assigns unique URLs to production/preview deployments too.
    allow_origin_regex=r"https://project-mzb0n(?:-[a-z0-9-]+)?\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

_PREVIEWS = {
    "before": "before.png",
    "after": "after.png",
    "change": "change.png",
}


def _run_or_404(run_id: str) -> dict:
    status = store.status(run_id)

    if status is None:
        raise HTTPException(404, f"Run '{run_id}' not found.")

    return status


@app.get("/api/health")
def health() -> dict:
    """Liveness plus which trained models exist on disk."""
    return {
        "status": "ok",
        "models_available": available_models(settings),
        "models_known": list(MODEL_NAMES),
        "evaluated": load_metrics(settings) is not None,
    }


@app.get("/api/metrics")
def metrics() -> JSONResponse:
    """Full evaluation report."""
    report = load_metrics(settings)

    if report is None:
        raise HTTPException(
            404,
            "Evaluation has not been run: storage/results/metrics.json "
            "does not exist. Fetch chips, train and evaluate (see README).",
        )

    return JSONResponse(report)


@app.post(
    "/api/detections",
    response_model=RunCreated,
    status_code=202,
)
def create_detection(body: DetectionIn) -> RunCreated:
    """Queue a detection run."""
    try:
        bbox = BBox(
            body.west,
            body.south,
            body.east,
            body.north,
        ).validate(settings.max_aoi_km)

    except InvalidAOI as exc:
        raise HTTPException(422, str(exc)) from exc

    request = DetectionRequest(
        bbox,
        body.before_year,
        body.after_year,
        (body.season_start_month, body.season_end_month),
        body.model,
    )

    return RunCreated(id=submit(store, settings, request))


@app.get("/api/detections")
def list_detections() -> list[dict]:
    """List detection runs."""
    return store.list()


@app.get("/api/detections/{run_id}")
def get_detection(run_id: str) -> dict:
    """Run status and completed result documents."""
    status = _run_or_404(run_id)

    result_file = store.path(run_id) / "result.json"

    if status["state"] == "done" and result_file.exists():
        status["result"], status["detections"] = load_run_documents(
            store.path(run_id)
        )

    return status


@app.get("/api/detections/{run_id}/images/{name}.png")
def get_image(run_id: str, name: str) -> FileResponse:
    """Retrieve a saved preview image."""
    _run_or_404(run_id)

    if name not in _PREVIEWS:
        raise HTTPException(404, "Image not available.")

    image_path = store.path(run_id) / _PREVIEWS[name]

    if not image_path.exists():
        raise HTTPException(404, "Image not available.")

    return FileResponse(image_path, media_type="image/png")


@app.get("/api/detections/{run_id}/report")
def get_report(run_id: str, format: str = "md"):
    """Download Markdown, PDF, or GeoJSON reports for a completed run."""
    status = _run_or_404(run_id)

    if status["state"] != "done":
        raise HTTPException(409, "Run has not finished.")

    result, detections = load_run_documents(store.path(run_id))

    if format == "geojson":
        return JSONResponse(
            detections,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{run_id}.geojson"'
                )
            },
        )

    if format == "pdf":
        pdf = build_pdf_report(run_id, result, detections, store.path(run_id))

        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{run_id}-report.pdf"'
                )
            },
        )

    if format != "md":
        raise HTTPException(
            422,
            "format must be 'md', 'pdf' or 'geojson'.",
        )

    return PlainTextResponse(
        build_markdown_report(run_id, result, detections),
        media_type="text/markdown",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{run_id}-report.md"'
            )
        },
    )
