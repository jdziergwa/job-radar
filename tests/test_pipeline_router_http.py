from fastapi.testclient import TestClient

from api.main import app
from api.routers import pipeline as pipeline_router


class _FakeStore:
    def __init__(self, metadata: dict[str, str]) -> None:
        self._metadata = metadata

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        return self._metadata.get(key, default)


def test_pipeline_endpoints_use_mocked_background_state(monkeypatch):
    calls: list[dict] = []

    async def fake_launch_pipeline(**kwargs):
        calls.append(kwargs)
        return "run-123"

    async def fake_cancel_pipeline(_run_id: str):
        return True

    async def fake_get_aggregator_metadata():
        return {
            "last_updated": "2026-04-10T08:00:00Z",
            "total_jobs": 5000,
        }

    monkeypatch.setattr(
        pipeline_router.bg,
        "get_active",
        lambda profile: "run-123" if calls else None,
    )
    monkeypatch.setattr(pipeline_router.bg, "launch_pipeline", fake_launch_pipeline)
    monkeypatch.setattr(pipeline_router.bg, "get_status", lambda run_id: {
        "status": "running",
        "step": 2,
        "step_name": "Hydrate",
        "detail": "Fetching descriptions",
        "duration": 4.2,
        "stats": {"new_jobs": 3},
        "skipped_steps": [1],
        "error": None,
    } if run_id == "run-123" else None)
    monkeypatch.setattr(pipeline_router.bg, "cancel_pipeline", fake_cancel_pipeline)
    monkeypatch.setattr(pipeline_router, "get_aggregator_metadata", fake_get_aggregator_metadata)
    monkeypatch.setattr(
        pipeline_router,
        "get_store",
        lambda profile="default": _FakeStore({"aggregator_version": "2026-04-10T08:00:00Z"}),
    )

    with TestClient(app) as client:
        run_response = client.post(
            "/api/pipeline/run",
            json={"profile": "default", "sources": ["local"], "dry_run": True},
        )
        status_response = client.get("/api/pipeline/status/run-123")
        active_response = client.get("/api/pipeline/active")
        cancel_response = client.post("/api/pipeline/cancel/run-123")
        aggregator_response = client.get("/api/pipeline/aggregator/status")

        assert run_response.status_code == 200
        assert run_response.json() == {"run_id": "run-123"}
        assert calls == [{"profile": "default", "sources": ["local"], "dry_run": True}]

        assert status_response.status_code == 200
        assert status_response.json()["status"] == "running"
        assert status_response.json()["step_name"] == "Hydrate"

        assert active_response.status_code == 200
        assert active_response.json() == {"running": True, "run_id": "run-123"}

        assert cancel_response.status_code == 200
        assert cancel_response.json() == {"status": "cancelling"}

        assert aggregator_response.status_code == 200
        assert aggregator_response.json()["is_up_to_date"] is True
        assert aggregator_response.json()["total_jobs"] == 5000


def test_pipeline_run_conflict_and_missing_status(monkeypatch):
    monkeypatch.setattr(pipeline_router.bg, "get_active", lambda profile: "run-busy")
    monkeypatch.setattr(pipeline_router.bg, "get_status", lambda run_id: {
        "status": "running",
        "step": 1,
        "step_name": "Collect",
        "detail": None,
        "duration": 1.0,
        "stats": None,
        "skipped_steps": [],
        "error": None,
    } if run_id == "run-busy" else None)

    with TestClient(app) as client:
        conflict_response = client.post("/api/pipeline/run", json={"profile": "default"})
        not_found_response = client.get("/api/pipeline/status/unknown-run")

        assert conflict_response.status_code == 409
        assert "already running" in conflict_response.json()["detail"]
        assert not_found_response.status_code == 200
        assert not_found_response.json()["status"] == "not_found"
