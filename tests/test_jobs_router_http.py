import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.routers import jobs as jobs_router
from src.models import RawJob
from src.store import Store


def _build_store() -> Store:
    tmpdir = tempfile.TemporaryDirectory()
    db_path = Path(tmpdir.name) / "jobs.db"
    store = Store(str(db_path))
    store._tmpdir = tmpdir  # keep temp dir alive for the test lifetime
    return store


def _seed_jobs(store: Store) -> int:
    store.upsert_jobs([
        RawJob(
            ats_platform="ashby",
            company_slug="acme",
            company_name="Acme",
            job_id="job-1",
            title="Senior QA Engineer",
            location="Remote",
            url="https://example.com/jobs/1",
            description="Own the test platform.",
            posted_at="2026-04-08T00:00:00Z",
            fetched_at="2026-04-08T00:00:00Z",
            match_tier="high_confidence",
        ),
        RawJob(
            ats_platform="lever",
            company_slug="globex",
            company_name="Globex",
            job_id="job-2",
            title="Backend Engineer",
            location="Berlin",
            url="https://example.com/jobs/2",
            description="Backend APIs.",
            posted_at="2026-04-08T00:00:00Z",
            fetched_at="2026-04-08T00:00:00Z",
        ),
    ])
    candidate = next(job for job in store.get_unscored() if job.job_id == "job-1")
    store.update_score(
        db_id=candidate.db_id,
        fit_score=82,
        reasoning="Strong fit for SDET scope.",
        breakdown={
            "tech_stack_match": 84,
            "seniority_match": 80,
            "remote_location_fit": 90,
            "growth_potential": 76,
        },
        fit_category="core_fit",
        apply_priority="medium",
    )
    return candidate.db_id


def test_jobs_endpoints_list_detail_and_status_update(monkeypatch):
    store = _build_store()
    scored_id = _seed_jobs(store)
    monkeypatch.setattr(jobs_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
        list_response = client.get(
            "/api/jobs",
            params={"status": "scored", "priority": "high", "search": "test platform"},
        )

        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["total"] == 1
        assert payload["jobs"][0]["id"] == scored_id
        assert payload["jobs"][0]["score_breakdown"]["apply_priority"] == "high"

        detail_response = client.get(f"/api/jobs/{scored_id}")

        assert detail_response.status_code == 200
        assert detail_response.json()["description"] == "Own the test platform."

        missing_response = client.get("/api/jobs/999999")

        assert missing_response.status_code == 404

        patch_response = client.patch(
            f"/api/jobs/{scored_id}/status",
            json={"status": "applied"},
        )

        assert patch_response.status_code == 200
        assert patch_response.json() == {"ok": True, "id": scored_id, "status": "applied"}
        assert store.get_job_detail(scored_id)["status"] == "applied"
        assert store.get_metadata("last_job_status_change_at") is not None


def test_jobs_rescore_endpoints_use_mocked_pipeline_launcher(monkeypatch):
    store = _build_store()
    scored_id = _seed_jobs(store)
    calls: list[dict] = []

    async def fake_launch_pipeline(**kwargs):
        calls.append(kwargs)
        return "run-123"

    monkeypatch.setattr(jobs_router, "get_store", lambda profile="default": store)
    monkeypatch.setattr(jobs_router.bg, "launch_pipeline", fake_launch_pipeline)

    with TestClient(app) as client:
        single_response = client.post(f"/api/jobs/{scored_id}/rescore")
        all_response = client.post("/api/jobs/rescore/all")

        assert single_response.status_code == 200
        assert single_response.json() == {"run_id": "run-123"}
        assert all_response.status_code == 200
        assert all_response.json() == {"run_id": "run-123"}

    assert calls == [
        {"profile": "default", "job_id": scored_id},
        {"profile": "default", "rescore_all": True},
    ]
