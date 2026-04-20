import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

from api.main import app
from api.routers import applications as applications_router
from api.routers import companies as companies_router
from api.routers import jobs as jobs_router
from src.models import RawJob
from src.store import Store


def _build_store() -> Store:
    tmpdir = tempfile.TemporaryDirectory()
    db_path = Path(tmpdir.name) / "jobs.db"
    store = Store(str(db_path))
    store._tmpdir = tmpdir  # keep temp dir alive for the test lifetime
    return store


def _seed_jobs(store: Store) -> dict[str, int]:
    store.upsert_jobs(
        [
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
        ]
    )
    seeded: dict[str, int] = {}
    for candidate in store.get_unscored():
        seeded[candidate.job_id] = candidate.db_id
        if candidate.job_id == "job-1":
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
    return seeded


def test_application_endpoints_lifecycle_stats_and_timeline(monkeypatch):
    store = _build_store()
    ids = _seed_jobs(store)
    job_id = ids["job-1"]
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
        invalid_transition = client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "offer"},
        )

        assert invalid_transition.status_code == 422

        applied_response = client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied", "note": "Sent via referral"},
        )

        assert applied_response.status_code == 200
        assert applied_response.json()["application_status"] == "applied"
        assert applied_response.json()["applied_at"] is not None

        notes_response = client.patch(
            f"/api/jobs/{job_id}/notes",
            json={"notes": "Strong referral from previous teammate."},
        )
        next_step_response = client.patch(
            f"/api/jobs/{job_id}/next-step",
            json={"next_step": "Recruiter call", "next_step_date": "2026-04-20"},
        )
        applied_at_response = client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        screening_response = client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "screening", "note": "Recruiter replied"},
        )
        response_date_response = client.patch(
            f"/api/jobs/{job_id}/response-date",
            json={"response_date": "2026-04-12"},
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")
        list_response = client.get("/api/applications", params={"status": "screening"})
        stats_response = client.get("/api/applications/stats")

        assert notes_response.status_code == 200
        assert notes_response.json()["notes"] == "Strong referral from previous teammate."
        assert next_step_response.status_code == 200
        assert next_step_response.json()["next_step"] == "Recruiter call"
        assert applied_at_response.status_code == 200
        assert applied_at_response.json()["applied_at"] == "2026-04-10"
        assert screening_response.status_code == 200
        assert screening_response.json()["application_status"] == "screening"
        assert response_date_response.status_code == 200
        assert response_date_response.json()["created_at"] == "2026-04-12"

        assert timeline_response.status_code == 200
        timeline_events = timeline_response.json()["events"]
        assert [event["status"] for event in timeline_events] == ["applied", "screening"]
        assert timeline_events[-1]["note"] == "Recruiter replied"
        assert timeline_events[-1]["created_at"] == "2026-04-12"

        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        listed_job = list_response.json()["jobs"][0]
        assert listed_job["id"] == job_id
        assert listed_job["days_since_applied"] is not None

        assert stats_response.status_code == 200
        stats_payload = stats_response.json()
        assert stats_payload["total"] == 1
        assert stats_payload["active_count"] == 1
        assert stats_payload["response_rate"] == 100.0
        assert stats_payload["status_counts"]["screening"] == 1

        remove_response = client.delete(f"/api/jobs/{job_id}/application-status")
        timeline_after_remove = client.get(f"/api/jobs/{job_id}/timeline")

    assert remove_response.status_code == 200
    assert remove_response.json()["application_status"] is None
    assert remove_response.json()["next_step"] is None
    assert remove_response.json()["notes"] is None
    assert timeline_after_remove.status_code == 200
    assert timeline_after_remove.json()["events"] == []


def test_timeline_events_can_be_retimed_and_deleted(monkeypatch):
    store = _build_store()
    ids = _seed_jobs(store)
    job_id = ids["job-1"]
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)
    monkeypatch.setattr(jobs_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied", "note": "Sent application"},
        )
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "screening", "note": "Recruiter replied"},
        )

        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")
        assert timeline_response.status_code == 200
        applied_event_id = timeline_response.json()["events"][0]["id"]
        screening_event_id = timeline_response.json()["events"][1]["id"]

        retime_response = client.patch(
            f"/api/jobs/{job_id}/timeline/{applied_event_id}",
            json={
                "created_at": "2026-04-09",
                "note": "Applied after recruiter follow-up",
            },
        )
        updated_job_response = client.get(f"/api/jobs/{job_id}")
        delete_response = client.delete(f"/api/jobs/{job_id}/timeline/{screening_event_id}")
        final_job_response = client.get(f"/api/jobs/{job_id}")

    assert retime_response.status_code == 200
    assert retime_response.json()["created_at"] == "2026-04-09"
    assert retime_response.json()["note"] == "Applied after recruiter follow-up"

    assert updated_job_response.status_code == 200
    assert updated_job_response.json()["applied_at"] == "2026-04-09"
    assert updated_job_response.json()["application_status"] == "screening"

    assert delete_response.status_code == 200
    assert [event["status"] for event in delete_response.json()["events"]] == ["applied"]

    assert final_job_response.status_code == 200
    assert final_job_response.json()["application_status"] == "applied"
    assert final_job_response.json()["applied_at"] == "2026-04-09"


def test_timeline_cannot_delete_only_applied_event(monkeypatch):
    store = _build_store()
    ids = _seed_jobs(store)
    job_id = ids["job-1"]
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")
        assert timeline_response.status_code == 200
        applied_event_id = timeline_response.json()["events"][0]["id"]

        delete_response = client.delete(f"/api/jobs/{job_id}/timeline/{applied_event_id}")

    assert delete_response.status_code == 422
    assert delete_response.json()["detail"] == "Cannot delete the only timeline event"


def test_timeline_can_create_custom_stage_and_update_projection(monkeypatch):
    store = _build_store()
    ids = _seed_jobs(store)
    job_id = ids["job-1"]
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)
    monkeypatch.setattr(jobs_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        create_response = client.post(
            f"/api/jobs/{job_id}/timeline",
            json={
                "canonical_phase": "interviewing",
                "stage_label": "Technical Interview",
                "occurred_at": "2026-04-11",
                "note": "System design round",
            },
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")
        job_response = client.get(f"/api/jobs/{job_id}")

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "interviewing"
    assert created["canonical_phase"] == "interviewing"
    assert created["stage_label"] == "Technical Interview"
    assert created["occurred_at"] == "2026-04-11"
    assert created["created_at"] == "2026-04-11"
    assert created["note"] == "System design round"

    assert timeline_response.status_code == 200
    events = timeline_response.json()["events"]
    assert [event["status"] for event in events] == ["applied", "interviewing"]
    assert events[-1]["stage_label"] == "Technical Interview"

    assert job_response.status_code == 200
    assert job_response.json()["application_status"] == "interviewing"
    assert job_response.json()["applied_at"] is not None


def test_timeline_patch_can_edit_phase_label_date_and_note(monkeypatch):
    store = _build_store()
    ids = _seed_jobs(store)
    job_id = ids["job-1"]
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)
    monkeypatch.setattr(jobs_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        created = client.post(
            f"/api/jobs/{job_id}/timeline",
            json={
                "canonical_phase": "screening",
                "stage_label": "Recruiter Screen",
                "occurred_at": "2026-04-11",
                "note": "Initial call",
            },
        )
        event_id = created.json()["id"]
        update_response = client.patch(
            f"/api/jobs/{job_id}/timeline/{event_id}",
            json={
                "canonical_phase": "interviewing",
                "stage_label": "Culture Interview",
                "occurred_at": "2026-04-12",
                "note": "Hiring manager and PM",
            },
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")
        job_response = client.get(f"/api/jobs/{job_id}")

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "interviewing"
    assert updated["canonical_phase"] == "interviewing"
    assert updated["stage_label"] == "Culture Interview"
    assert updated["occurred_at"] == "2026-04-12"
    assert updated["created_at"] == "2026-04-12"
    assert updated["note"] == "Hiring manager and PM"

    assert timeline_response.status_code == 200
    events = timeline_response.json()["events"]
    assert [event["status"] for event in events] == ["applied", "interviewing"]
    assert events[-1]["stage_label"] == "Culture Interview"

    assert job_response.status_code == 200
    assert job_response.json()["application_status"] == "interviewing"


def test_application_import_endpoint_handles_fetch_duplicates_and_manual_fallback(monkeypatch):
    store = _build_store()
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    async def fake_fetch_job_from_url(url: str):
        assert "greenhouse" in url
        return RawJob(
            ats_platform="greenhouse",
            company_slug="example-team",
            company_name="Example Team",
            job_id="12345",
            title="Senior QA Engineer",
            location="Remote",
            url="https://boards.greenhouse.io/example-team/jobs/12345",
            description="Test all the things.",
            posted_at=None,
            fetched_at="2026-04-18T00:00:00Z",
            company_metadata={"quality_signals": ["Top-tier product team"]},
            location_metadata={"workplace_type": "Remote"},
            salary="$180k - $220k",
            salary_min=180000,
            salary_max=220000,
            salary_currency="USD",
        )

    monkeypatch.setattr(applications_router, "fetch_job_from_url", fake_fetch_job_from_url)

    with TestClient(app) as client:
        first_import = client.post(
            "/api/applications/import",
            json={
                "url": "https://boards.greenhouse.io/example-team/jobs/12345",
                "applied_at": "2026-04-05",
                "notes": "Saved from external search",
            },
        )
        duplicate_import = client.post(
            "/api/applications/import",
            json={"url": "https://boards.greenhouse.io/example-team/jobs/12345"},
        )
        timeline_response = client.get(f"/api/jobs/{first_import.json()['job_id']}/timeline")

        assert first_import.status_code == 200
        first_payload = first_import.json()
        assert first_payload["fetched"] is True
        assert first_payload["already_tracked"] is False
        assert first_payload["job"]["application_status"] == "applied"
        assert first_payload["job"]["applied_at"] == "2026-04-05"
        assert first_payload["job"]["source"] == "manual"
        assert first_payload["job"]["salary"] == "$180k - $220k"

        assert duplicate_import.status_code == 200
        assert duplicate_import.json()["already_tracked"] is True
        assert timeline_response.status_code == 200
        assert timeline_response.json()["events"][0]["status"] == "applied"
        assert timeline_response.json()["events"][0]["created_at"] == "2026-04-05"

        async def failed_fetch_job_from_url(url: str):
            return None

        monkeypatch.setattr(applications_router, "fetch_job_from_url", failed_fetch_job_from_url)

        missing_details = client.post(
            "/api/applications/import",
            json={"url": "https://jobs.example.com/role/abc"},
        )
        external_import = client.post(
            "/api/applications/import",
            json={
                "url": "https://jobs.example.com/role/abc",
                "company_name": "Example Inc",
                "title": "QA Lead",
                "location": "Remote",
            },
        )

    assert missing_details.status_code == 200
    assert missing_details.json() == {
        "job_id": None,
        "fetched": False,
        "needs_manual_entry": True,
        "already_tracked": False,
        "job": None,
    }

    assert external_import.status_code == 200
    external_payload = external_import.json()
    assert external_payload["fetched"] is False
    assert external_payload["already_tracked"] is False
    assert external_payload["job"]["ats_platform"] == "external"
    assert external_payload["job"]["company_slug"] == "example-inc"
    assert len(store.get_job_detail(external_payload["job_id"])["job_id"]) == 16

    imported_row = store.get_job_detail(first_payload["job_id"])
    assert imported_row["applied_at"] == "2026-04-05"
    assert json.loads(imported_row["company_metadata"]) == {"quality_signals": ["Top-tier product team"]}
    assert json.loads(imported_row["location_metadata"]) == {"workplace_type": "Remote"}
    assert imported_row["salary_min"] == 180000
    assert imported_row["salary_max"] == 220000
    assert imported_row["salary_currency"] == "USD"


def test_application_status_allows_stepping_back_one_stage(monkeypatch):
    store = _build_store()
    ids = _seed_jobs(store)
    job_id = ids["job-1"]
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
      client.patch(
          f"/api/jobs/{job_id}/application-status",
          json={"application_status": "applied"},
      )
      forward = client.patch(
          f"/api/jobs/{job_id}/application-status",
          json={"application_status": "screening", "note": "Recruiter replied"},
      )
      backward = client.patch(
          f"/api/jobs/{job_id}/application-status",
          json={"application_status": "applied", "note": "Clicked screening by mistake"},
      )
      timeline = client.get(f"/api/jobs/{job_id}/timeline")

    assert forward.status_code == 200
    assert backward.status_code == 200
    assert backward.json()["application_status"] == "applied"
    assert [event["status"] for event in timeline.json()["events"]] == ["applied", "screening", "applied"]
    assert timeline.json()["events"][-1]["note"] == "Clicked screening by mistake"


def test_application_import_retracks_existing_identity_after_tracker_removal(monkeypatch):
    store = _build_store()
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    async def fake_fetch_job_from_url(url: str):
        return RawJob(
            ats_platform="greenhouse",
            company_slug="example-team",
            company_name="Example Team",
            job_id="12345",
            title="Senior QA Engineer",
            location="Remote",
            url="https://boards.greenhouse.io/example-team/jobs/12345",
            description="Test all the things.",
            posted_at=None,
            fetched_at="2026-04-18T00:00:00Z",
        )

    monkeypatch.setattr(applications_router, "fetch_job_from_url", fake_fetch_job_from_url)

    with TestClient(app) as client:
        first_import = client.post(
            "/api/applications/import",
            json={
                "url": "https://boards.greenhouse.io/example-team/jobs/12345",
                "applied_at": "2026-04-05",
            },
        )
        job_id = first_import.json()["job_id"]

        remove_response = client.delete(f"/api/jobs/{job_id}/application-status")
        second_import = client.post(
            "/api/applications/import",
            json={"url": "https://boards.greenhouse.io/example-team/jobs/12345", "notes": "Re-added after reconsidering"},
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")

    assert first_import.status_code == 200
    assert remove_response.status_code == 200
    assert second_import.status_code == 200
    second_payload = second_import.json()
    assert second_payload["job_id"] == job_id
    assert second_payload["already_tracked"] is False
    assert second_payload["job"]["application_status"] == "applied"
    assert second_payload["job"]["notes"] == "Re-added after reconsidering"

    assert timeline_response.status_code == 200
    assert [event["status"] for event in timeline_response.json()["events"]] == ["applied"]
    assert timeline_response.json()["events"][0]["created_at"] != "2026-04-05"


def test_manual_application_import_persists_manual_identity_and_salary(monkeypatch):
    store = _build_store()
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    with TestClient(app) as client:
        response = client.post(
            "/api/applications/import/manual",
            json={
                "company_name": "Example Manual Company",
                "title": "QA Lead",
                "location": "Berlin",
                "applied_at": "2026-04-01",
                "description": "Own release quality.",
                "salary": "$150k",
                "notes": "Warm intro from recruiter.",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["already_tracked"] is False
    assert payload["job"]["ats_platform"] == "manual"
    assert payload["job"]["company_slug"] == "example-manual-company"
    assert payload["job"]["application_status"] == "applied"
    assert payload["job"]["applied_at"] == "2026-04-01"
    assert payload["job"]["salary"] == "$150k"
    assert payload["job"]["url"].startswith("manual://example-manual-company/")


def test_application_import_can_add_company_to_pipeline(monkeypatch):
    store = _build_store()
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        profile_dir = base_dir / "default"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "companies.yaml").write_text(
            yaml.safe_dump({"greenhouse": []}, sort_keys=False),
            encoding="utf-8",
        )

        original_profiles_dir = companies_router.PROFILES_DIR
        companies_router.PROFILES_DIR = base_dir

        async def fake_fetch_job_from_url(url: str):
            return RawJob(
                ats_platform="greenhouse",
                company_slug="example-team",
                company_name="Example Team",
                job_id="12345",
                title="Senior QA Engineer",
                location="Remote",
                url="https://boards.greenhouse.io/example-team/jobs/12345",
                description="Test all the things.",
                posted_at=None,
                fetched_at="2026-04-18T00:00:00Z",
            )

        monkeypatch.setattr(applications_router, "fetch_job_from_url", fake_fetch_job_from_url)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/applications/import",
                    json={
                        "url": "https://boards.greenhouse.io/example-team/jobs/12345",
                        "track_company_in_pipeline": True,
                    },
                )
        finally:
            companies_router.PROFILES_DIR = original_profiles_dir

        saved = yaml.safe_load((profile_dir / "companies.yaml").read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert saved["greenhouse"] == [{"slug": "example-team", "name": "Example Team"}]


def test_application_import_does_not_add_import_only_workday_company_to_pipeline(monkeypatch):
    store = _build_store()
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        profile_dir = base_dir / "default"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "companies.yaml").write_text(
            yaml.safe_dump({"greenhouse": []}, sort_keys=False),
            encoding="utf-8",
        )

        original_profiles_dir = companies_router.PROFILES_DIR
        companies_router.PROFILES_DIR = base_dir

        async def fake_fetch_job_from_url(url: str):
            return RawJob(
                ats_platform="workday",
                company_slug="exampleco",
                company_name="Example Co",
                job_id="Staff-Quality-Engineer_R-12345-1",
                title="Staff Quality Engineer",
                location="London",
                url="https://exampleco.wd12.myworkdayjobs.com/ExampleBoard/job/Remote/Staff-Quality-Engineer_R-12345-1",
                description="Drive quality strategy across product surfaces.",
                posted_at="2026-04-19",
                fetched_at="2026-04-19T00:00:00Z",
            )

        monkeypatch.setattr(applications_router, "fetch_job_from_url", fake_fetch_job_from_url)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/applications/import",
                    json={
                        "url": "https://exampleco.wd12.myworkdayjobs.com/en-US/ExampleBoard/job/Remote/Staff-Quality-Engineer_R-12345-1",
                        "track_company_in_pipeline": True,
                    },
                )
        finally:
            companies_router.PROFILES_DIR = original_profiles_dir

        saved = yaml.safe_load((profile_dir / "companies.yaml").read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert saved["greenhouse"] == []
    assert "workday" not in saved


def test_application_import_refreshes_existing_sparse_job_from_fetched_data(monkeypatch):
    store = _build_store()
    monkeypatch.setattr(applications_router, "get_store", lambda profile="default": store)

    created, _ = store.import_job(
        ats_platform="bamboohr",
        company_slug="example-team",
        external_job_id="155",
        company_name="Example Team",
        title="Example Team",
        location="",
        url="https://example-team.bamboohr.com/careers/155",
        description="",
        source="manual",
        initial_event_note="Imported from URL",
    )

    async def fake_fetch_job_from_url(url: str):
        assert url == "https://example-team.bamboohr.com/careers/155"
        return RawJob(
            ats_platform="bamboohr",
            company_slug="example-team",
            company_name="Example Team",
            job_id="155",
            title="Senior Software Engineer in Test",
            location="London",
            url="https://example-team.bamboohr.com/careers/155",
            description="<p>Build resilient quality systems.</p>",
            posted_at="2026-04-19",
            fetched_at="2026-04-19T10:00:00Z",
        )

    monkeypatch.setattr(applications_router, "fetch_job_from_url", fake_fetch_job_from_url)

    with TestClient(app) as client:
        response = client.post(
            "/api/applications/import",
            json={"url": "https://example-team.bamboohr.com/careers/155"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["already_tracked"] is True
    assert payload["job_id"] == created["id"]
    assert payload["job"]["title"] == "Senior Software Engineer in Test"
    assert payload["job"]["location"] == "London"

    refreshed = store.get_job_detail(created["id"])
    assert refreshed["title"] == "Senior Software Engineer in Test"
    assert refreshed["location"] == "London"
    assert refreshed["description"] == "<p>Build resilient quality systems.</p>"
