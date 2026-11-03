import time

import pytest
from fastapi.testclient import TestClient

from sylvan.api.main import app

client = TestClient(app)
VALID = {"west": 79.30, "south": 13.60, "east": 79.36, "north": 13.66, "before_year": 2019, "after_year": 2023,
         "season_start_month": 1, "season_end_month": 4, "model": "best"}


def test_health_reports_no_models_on_fresh_storage():
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["models_available"] == [] and body["evaluated"] is False


def test_metrics_404_explains_missing_evaluation():
    response = client.get("/api/metrics")
    assert response.status_code == 404 and "Evaluation has not been run" in response.json()["detail"]


@pytest.mark.parametrize("patch,fragment", [
    ({"east": 79.20}, "west < east"),
    ({"east": 79.80}, "limit"),
    ({"after_year": 2019}, "later"),
    ({"season_end_month": 0}, ""),
    ({"model": "gpt"}, ""),
])
def test_invalid_requests_are_rejected(patch, fragment):
    response = client.post("/api/detections", json={**VALID, **patch})
    assert response.status_code == 422
    assert fragment in str(response.json())


def test_unavailable_model_fails_cleanly_before_any_download():
    created = client.post("/api/detections", json={**VALID, "model": "random_forest"})
    assert created.status_code == 202
    run_id = created.json()["id"]
    for _ in range(50):
        status = client.get(f"/api/detections/{run_id}").json()
        if status["state"] in ("failed", "done"):
            break
        time.sleep(0.1)
    assert status["state"] == "failed" and "not trained" in status["error"]
    assert client.get(f"/api/detections/{run_id}/report").status_code == 409
    assert any(r["id"] == run_id for r in client.get("/api/detections").json())


def test_unknown_run_is_404():
    assert client.get("/api/detections/nope").status_code == 404
