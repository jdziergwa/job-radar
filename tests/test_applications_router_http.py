import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import yaml

from api.main import app
from api.routers import applications as applications_router
from api.routers import companies as companies_router
from api.routers import jobs as jobs_router
from src.models import RawJob

pytestmark = pytest.mark.api


def test_application_endpoints_lifecycle_stats_and_timeline(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router)

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
        next_stage_response = client.patch(
            f"/api/jobs/{job_id}/next-stage",
            json={"stage_label": "Recruiter call", "scheduled_for": "2026-04-20"},
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
        assert next_stage_response.status_code == 200
        assert next_stage_response.json()["next_stage_label"] == "Recruiter call"
        assert next_stage_response.json()["next_stage_date"] == "2026-04-20"
        assert applied_at_response.status_code == 200
        assert applied_at_response.json()["applied_at"] == "2026-04-10"
        assert screening_response.status_code == 200
        assert screening_response.json()["application_status"] == "screening"
        assert response_date_response.status_code == 200
        assert response_date_response.json()["event_type"] == "response_received"
        assert response_date_response.json()["created_at"] == "2026-04-12"

        assert timeline_response.status_code == 200
        timeline_events = timeline_response.json()["events"]
        assert [event["status"] for event in timeline_events] == ["applied", "response_received", "screening"]
        assert timeline_events[1]["event_type"] == "response_received"
        assert timeline_events[-1]["note"] == "Recruiter replied"
        assert timeline_events[1]["created_at"] == "2026-04-12"

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
    assert remove_response.json()["next_stage_label"] is None
    assert remove_response.json()["next_stage_date"] is None
    assert remove_response.json()["notes"] is None
    assert timeline_after_remove.status_code == 200
    assert timeline_after_remove.json()["events"] == []


def test_scheduling_next_stage_can_record_response_milestone_without_advancing_stage(
    seed_sample_jobs,
    bind_store,
):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router, jobs_router)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        schedule_response = client.patch(
            f"/api/jobs/{job_id}/next-stage",
            json={
                "canonical_phase": "screening",
                "stage_label": "Recruiter Call",
                "scheduled_for": "2026-04-20",
                "note": "Booked with recruiter",
                "mark_responded": True,
                "response_date": "2026-04-12",
            },
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")
        stats_before_complete = client.get("/api/applications/stats")
        list_before_complete = client.get("/api/applications", params={"status": "applied"})
        complete_response = client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "screening"},
        )
        timeline_after_complete = client.get(f"/api/jobs/{job_id}/timeline")
        job_after_complete = client.get(f"/api/jobs/{job_id}")

    assert schedule_response.status_code == 200
    scheduled_job = schedule_response.json()
    assert scheduled_job["application_status"] == "applied"
    assert scheduled_job["next_stage_label"] == "Recruiter Call"
    assert scheduled_job["next_stage_date"] == "2026-04-20"
    assert scheduled_job["next_stage_canonical_phase"] == "screening"

    assert timeline_response.status_code == 200
    scheduled_events = timeline_response.json()["events"]
    assert [event["status"] for event in scheduled_events] == ["applied", "response_received", "screening"]
    assert [event["event_type"] for event in scheduled_events] == ["stage", "response_received", "stage"]
    assert [event["lifecycle_state"] for event in scheduled_events] == ["completed", "completed", "scheduled"]
    assert scheduled_events[1]["stage_label"] == "Response received"
    assert scheduled_events[1]["created_at"] == "2026-04-12"
    assert scheduled_events[-1]["stage_label"] == "Recruiter Call"
    assert scheduled_events[-1]["scheduled_for"] == "2026-04-20"
    assert scheduled_events[-1]["occurred_at"] is None
    assert scheduled_events[-1]["note"] == "Booked with recruiter"

    assert stats_before_complete.status_code == 200
    stats_payload = stats_before_complete.json()
    assert stats_payload["status_counts"]["applied"] == 1
    assert stats_payload["funnel"]["screening"] == 0
    assert stats_payload["response_rate"] == 100.0
    assert stats_payload["avg_time_to_response_days"] == 2.0

    assert list_before_complete.status_code == 200
    listed_job = list_before_complete.json()["jobs"][0]
    assert listed_job["application_status"] == "applied"
    assert listed_job["latest_stage_label"] == "Applied"

    assert complete_response.status_code == 200
    assert complete_response.json()["application_status"] == "screening"
    assert complete_response.json()["next_stage_label"] is None
    assert complete_response.json()["next_stage_date"] is None

    assert timeline_after_complete.status_code == 200
    completed_events = timeline_after_complete.json()["events"]
    assert [event["status"] for event in completed_events] == ["applied", "response_received", "screening"]
    assert [event["event_type"] for event in completed_events] == ["stage", "response_received", "stage"]
    assert [event["lifecycle_state"] for event in completed_events] == ["completed", "completed", "completed"]
    assert completed_events[-1]["stage_label"] == "Recruiter Call"
    assert completed_events[-1]["scheduled_for"] is None
    assert completed_events[-1]["occurred_at"] is not None

    assert job_after_complete.status_code == 200
    assert job_after_complete.json()["application_status"] == "screening"
    assert job_after_complete.json()["next_stage_label"] is None


def test_response_date_updates_explicit_response_milestone_when_present(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        client.patch(
            f"/api/jobs/{job_id}/next-stage",
            json={
                "canonical_phase": "screening",
                "stage_label": "Recruiter Call",
                "scheduled_for": "2026-04-20",
                "mark_responded": True,
                "response_date": "2026-04-12",
            },
        )

        response_date_response = client.patch(
            f"/api/jobs/{job_id}/response-date",
            json={"response_date": "2026-04-13"},
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")

    assert response_date_response.status_code == 200
    updated = response_date_response.json()
    assert updated["event_type"] == "response_received"
    assert updated["created_at"] == "2026-04-13"

    assert timeline_response.status_code == 200
    events = timeline_response.json()["events"]
    assert [event["status"] for event in events] == ["applied", "response_received", "screening"]
    assert events[1]["created_at"] == "2026-04-13"


def test_application_status_update_accepts_explicit_occurred_at(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )

        rejected_response = client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={
                "application_status": "rejected_by_company",
                "note": "Closed after final review",
                "occurred_at": "2026-04-18",
            },
        )
        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")

    assert rejected_response.status_code == 200
    assert rejected_response.json()["application_status"] == "rejected_by_company"

    assert timeline_response.status_code == 200
    events = timeline_response.json()["events"]
    assert [event["status"] for event in events] == ["applied", "rejected_by_company"]
    assert events[-1]["created_at"] == "2026-04-18"
    assert events[-1]["occurred_at"] == "2026-04-18"
    assert events[-1]["note"] == "Closed after final review"


def test_application_list_uses_latest_completed_activity_for_momentum(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied", "occurred_at": "2026-04-10"},
        )
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "screening", "occurred_at": "2026-04-17"},
        )

        list_response = client.get("/api/applications", params={"status": "screening"})

    assert list_response.status_code == 200
    listed_job = list_response.json()["jobs"][0]
    assert listed_job["id"] == job_id
    assert listed_job["latest_activity_at"] == "2026-04-17"
    assert listed_job["first_screen_at"] == "2026-04-17"


def test_timeline_events_can_be_retimed_and_deleted(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router, jobs_router)

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


def test_stage_retime_ignores_explicit_response_milestone_for_ordering(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        client.patch(
            f"/api/jobs/{job_id}/response-date",
            json={"response_date": "2026-04-12"},
        )
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "screening", "note": "Recruiter replied"},
        )

        timeline_response = client.get(f"/api/jobs/{job_id}/timeline")
        assert timeline_response.status_code == 200
        screening_event_id = timeline_response.json()["events"][-1]["id"]

        retime_response = client.patch(
            f"/api/jobs/{job_id}/timeline/{screening_event_id}",
            json={"created_at": "2026-04-11"},
        )
        updated_timeline = client.get(f"/api/jobs/{job_id}/timeline")

    assert retime_response.status_code == 200
    assert retime_response.json()["created_at"] == "2026-04-11"

    assert updated_timeline.status_code == 200
    assert [event["status"] for event in updated_timeline.json()["events"]] == ["applied", "screening", "response_received"]


def test_timeline_cannot_delete_only_applied_event(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router)

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


def test_timeline_can_create_custom_stage_and_update_projection(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router, jobs_router)

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


def test_timeline_patch_can_edit_phase_label_date_and_note(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router, jobs_router)

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


def test_applications_list_exposes_latest_custom_stage_label(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router, jobs_router)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        client.post(
            f"/api/jobs/{job_id}/timeline",
            json={
                "canonical_phase": "interviewing",
                "stage_label": "Technical Interview",
                "occurred_at": "2026-04-12",
            },
        )

        list_response = client.get("/api/applications", params={"status": "interviewing"})

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    listed_job = payload["jobs"][0]
    assert listed_job["application_status"] == "interviewing"
    assert listed_job["latest_stage_label"] == "Technical Interview"


def test_application_stats_use_timeline_history_for_response_metrics(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router, jobs_router)

    with TestClient(app) as client:
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "applied"},
        )
        client.patch(
            f"/api/jobs/{job_id}/applied-at",
            json={"applied_at": "2026-04-10"},
        )
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "screening"},
        )
        client.patch(
            f"/api/jobs/{job_id}/response-date",
            json={"response_date": "2026-04-12"},
        )
        client.patch(
            f"/api/jobs/{job_id}/application-status",
            json={"application_status": "rejected_by_user"},
        )

        stats_response = client.get("/api/applications/stats")

    assert stats_response.status_code == 200
    payload = stats_response.json()
    assert payload["total"] == 1
    assert payload["status_counts"]["rejected_by_user"] == 1
    assert payload["response_rate"] == 100.0
    assert payload["avg_time_to_response_days"] == 2.0
    assert payload["funnel"]["screening"] == 1


def test_application_import_endpoint_handles_fetch_duplicates_and_manual_fallback(store, bind_store, monkeypatch):
    bind_store(applications_router)

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
        assert first_payload["already_exists"] is False
        assert first_payload["already_tracked"] is False
        assert first_payload["job"]["application_status"] == "applied"
        assert first_payload["job"]["applied_at"] == "2026-04-05"
        assert first_payload["job"]["source"] == "manual"
        assert first_payload["job"]["salary"] == "$180k - $220k"

        assert duplicate_import.status_code == 200
        assert duplicate_import.json()["already_exists"] is True
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
        "already_exists": False,
        "already_tracked": False,
        "job": None,
    }

    assert external_import.status_code == 200
    external_payload = external_import.json()
    assert external_payload["fetched"] is False
    assert external_payload["already_exists"] is False
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


def test_application_status_allows_stepping_back_one_stage(seed_sample_jobs, bind_store):
    job_id = seed_sample_jobs()["job-1"]
    bind_store(applications_router)

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


def test_application_import_retracks_existing_identity_after_tracker_removal(store, bind_store, monkeypatch):
    bind_store(applications_router)

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
    assert second_payload["already_exists"] is True
    assert second_payload["already_tracked"] is False
    assert second_payload["job"]["application_status"] == "applied"
    assert second_payload["job"]["notes"] == "Re-added after reconsidering"

    assert timeline_response.status_code == 200
    assert [event["status"] for event in timeline_response.json()["events"]] == ["applied"]
    assert timeline_response.json()["events"][0]["created_at"] != "2026-04-05"


def test_manual_application_import_persists_manual_identity_and_salary(bind_store):
    bind_store(applications_router)

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
    assert payload["already_exists"] is False
    assert payload["already_tracked"] is False
    assert payload["job"]["ats_platform"] == "manual"
    assert payload["job"]["company_slug"] == "example-manual-company"
    assert payload["job"]["application_status"] == "applied"
    assert payload["job"]["applied_at"] == "2026-04-01"
    assert payload["job"]["salary"] == "$150k"
    assert payload["job"]["url"] == ""


def test_application_import_can_add_company_to_pipeline(bind_store, monkeypatch):
    bind_store(applications_router)

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


def test_application_import_does_not_add_import_only_workday_company_to_pipeline(bind_store, monkeypatch):
    bind_store(applications_router)

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


def test_application_import_refreshes_existing_sparse_job_from_fetched_data(store, bind_store, monkeypatch):
    bind_store(applications_router)

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
    assert payload["already_exists"] is True
    assert payload["already_tracked"] is True
    assert payload["job_id"] == created["id"]
    assert payload["job"]["title"] == "Senior Software Engineer in Test"
    assert payload["job"]["location"] == "London"

    refreshed = store.get_job_detail(created["id"])
    assert refreshed["title"] == "Senior Software Engineer in Test"
    assert refreshed["location"] == "London"
    assert refreshed["description"] == "<p>Build resilient quality systems.</p>"


def test_application_import_can_save_job_to_board_without_tracker_state(store, bind_store, monkeypatch):
    bind_store(applications_router, jobs_router)

    async def fake_fetch_job_from_url(url: str):
        assert url == "https://boards.greenhouse.io/example-team/jobs/12345"
        return RawJob(
            ats_platform="greenhouse",
            company_slug="example-team",
            company_name="Example Team",
            job_id="12345",
            title="Senior QA Engineer",
            location="Remote",
            url=url,
            description="Test all the things.",
            posted_at=None,
            fetched_at="2026-04-18T00:00:00Z",
        )

    monkeypatch.setattr(applications_router, "fetch_job_from_url", fake_fetch_job_from_url)

    with TestClient(app) as client:
        response = client.post(
            "/api/applications/import",
            json={
                "url": "https://boards.greenhouse.io/example-team/jobs/12345",
                "add_to_tracker": False,
                "notes": "Found externally",
                "applied_at": "2026-04-05",
            },
        )
        assert response.status_code == 200

        payload = response.json()
        timeline_response = client.get(f"/api/jobs/{payload['job_id']}/timeline")
        board_response = client.get(
            "/api/jobs",
            params={"status": "new", "tracked_mode": "exclude"},
        )

    assert payload["already_exists"] is False
    assert payload["already_tracked"] is False
    assert payload["job"]["application_status"] is None
    assert payload["job"]["applied_at"] is None
    assert payload["job"]["notes"] == "Found externally"
    assert timeline_response.status_code == 200
    assert timeline_response.json()["events"] == []
    assert any(job["id"] == payload["job_id"] for job in board_response.json()["jobs"])

    stored = store.get_job_detail(payload["job_id"])
    assert stored is not None
    assert stored["application_status"] is None
    assert stored["applied_at"] is None
