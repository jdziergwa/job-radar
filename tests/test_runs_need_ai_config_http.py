import pytest

from api.routers import jobs as jobs_router
from api.routers import pipeline as pipeline_router


pytestmark = pytest.mark.api


@pytest.fixture
def launches(monkeypatch):
    calls: list[dict] = []

    async def fake_launch_pipeline(**kwargs):
        calls.append(kwargs)
        return "run-123"

    monkeypatch.setattr(pipeline_router.bg, "launch_pipeline", fake_launch_pipeline)
    monkeypatch.setattr(pipeline_router.bg, "get_active", lambda profile: None)
    return calls


def test_scoring_run_without_ai_config_is_503_and_starts_nothing(no_ai_key, launches, client):
    response = client.post("/api/pipeline/run", json={"profile": "default", "sources": ["local"], "dry_run": False})

    assert response.status_code == 503
    assert response.json()["detail"].startswith("AI not configured: ")
    assert launches == []


def test_dry_run_without_ai_config_is_accepted(no_ai_key, launches, client):
    response = client.post("/api/pipeline/run", json={"profile": "default", "sources": ["local"], "dry_run": True})

    assert response.status_code == 200
    assert len(launches) == 1


def test_single_job_rescore_without_ai_config_is_503_and_starts_nothing(no_ai_key, launches, seed_sample_jobs, bind_store, client):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(jobs_router)

    response = client.post(f"/api/jobs/{job_id}/rescore")

    assert response.status_code == 503
    assert response.json()["detail"].startswith("AI not configured: ")
    assert launches == []


def test_scoped_rescore_without_ai_config_is_503_and_starts_nothing(no_ai_key, launches, bind_store, client):
    bind_store(jobs_router)

    response = client.post("/api/jobs/rescore", json={"scope": "failed_recent", "days": 3})

    assert response.status_code == 503
    assert response.json()["detail"].startswith("AI not configured: ")
    assert launches == []
