import pytest

from api.routers import jobs as jobs_router


pytestmark = pytest.mark.api


def test_jobs_endpoints_list_detail_and_status_update(store, seed_sample_jobs, bind_store, client):
    scored_id = seed_sample_jobs()["job-1"]
    bind_store(jobs_router)

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
        json={"status": "dismissed"},
    )

    assert patch_response.status_code == 200
    assert patch_response.json() == {"ok": True, "id": scored_id, "status": "dismissed"}
    assert store.get_job_detail(scored_id)["status"] == "dismissed"
    assert store.get_metadata("last_job_status_change_at") is not None


def test_jobs_list_tracked_mode_filters(store, seed_sample_jobs, bind_store, client):
    ids = seed_sample_jobs()
    scored_id = ids["job-1"]
    other_id = next(job.db_id for job in store.get_unscored() if job.job_id == "job-2")
    assert store.update_application_status(scored_id, "applied")
    bind_store(jobs_router)

    only_tracked = client.get("/api/jobs", params={"tracked_mode": "only"})
    exclude_tracked = client.get("/api/jobs", params={"tracked_mode": "exclude"})

    assert only_tracked.status_code == 200
    assert [job["id"] for job in only_tracked.json()["jobs"]] == [scored_id]
    assert exclude_tracked.status_code == 200
    assert [job["id"] for job in exclude_tracked.json()["jobs"]] == [other_id]


def test_jobs_rescore_endpoints_use_mocked_pipeline_launcher(seed_sample_jobs, bind_store, client, monkeypatch):
    scored_id = seed_sample_jobs()["job-1"]
    calls: list[dict] = []

    async def fake_launch_pipeline(**kwargs):
        calls.append(kwargs)
        return "run-123"

    bind_store(jobs_router)
    monkeypatch.setattr(jobs_router.bg, "launch_pipeline", fake_launch_pipeline)

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


def test_delete_job_allows_manual_imports_and_rejects_pipeline_jobs(store, seed_sample_jobs, bind_store, client):
    scored_id = seed_sample_jobs()["job-1"]

    manual_job, _ = store.import_job(
        ats_platform="manual",
        company_slug="example-manual-company",
        external_job_id="manual-delete-target",
        company_name="Example Manual Company",
        title="QA Lead",
        location="Remote",
        url="manual://example-manual-company/manual-delete-target",
        description="Temporary imported job.",
        notes="Delete me",
        source="manual",
        initial_event_note="Manually added",
    )
    manual_id = manual_job["id"]

    bind_store(jobs_router)

    forbidden_response = client.delete(f"/api/jobs/{scored_id}")
    allowed_response = client.delete(f"/api/jobs/{manual_id}")
    deleted_detail = client.get(f"/api/jobs/{manual_id}")

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "Only manually imported jobs can be deleted"
    assert allowed_response.status_code == 200
    assert allowed_response.json() == {"ok": True, "id": manual_id}
    assert deleted_detail.status_code == 404
    assert store.get_job_detail(manual_id) is None

    with store._connect() as conn:
        event_count = conn.execute(
            "SELECT COUNT(*) FROM application_events WHERE job_id = ?",
            (manual_id,),
        ).fetchone()[0]
    assert event_count == 0


def test_jobs_endpoints_expose_fresh_flag_since_previous_collection_run(store, seed_sample_jobs, bind_store, client):
    ids = seed_sample_jobs()
    fresh_id = ids["job-1"]
    older_id = next(job.db_id for job in store.get_unscored() if job.job_id == "job-2")

    store.set_metadata("previous_collection_run_at", "2026-04-10T12:00:00")
    with store._connect() as conn:
        conn.execute(
            "UPDATE jobs SET first_seen_at = ? WHERE id = ?",
            ("2026-04-10T14:00:00", fresh_id),
        )
        conn.execute(
            "UPDATE jobs SET first_seen_at = ? WHERE id = ?",
            ("2026-04-10T10:00:00", older_id),
        )

    bind_store(jobs_router)

    list_response = client.get("/api/jobs", params={"sort": "date", "order": "desc"})
    detail_response = client.get(f"/api/jobs/{fresh_id}")

    assert list_response.status_code == 200
    jobs_by_id = {job["id"]: job for job in list_response.json()["jobs"]}
    assert jobs_by_id[fresh_id]["is_fresh"] is True
    assert jobs_by_id[older_id]["is_fresh"] is False

    assert detail_response.status_code == 200
    assert detail_response.json()["is_fresh"] is True
