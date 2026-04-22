from datetime import datetime
from unittest.mock import patch

from api.routers import applications as applications_router


class _FakeApplicationsStore:
    def __init__(self) -> None:
        self._metadata: dict[str, str] = {
            "last_pipeline_run_at": "2026-04-18T10:00:00",
        }
        self._application_rows = [
            {
                "id": 1,
                "ats_platform": "manual",
                "company_slug": "example-manual-company",
                "company_name": "Example Manual Company",
                "title": "QA Lead",
                "location": "Berlin",
                "url": "",
                "posted_at": None,
                "first_seen_at": "2026-04-18T10:00:00",
                "last_seen_at": "2026-04-18T10:00:00",
                "fit_score": None,
                "score_reasoning": None,
                "score_breakdown": None,
                "scored_at": None,
                "status": "new",
                "application_status": "applied",
                "applied_at": "2026-04-18T10:00:00",
                "notes": None,
                "next_stage_label": None,
                "next_stage_date": None,
                "next_stage_canonical_phase": None,
                "next_stage_note": None,
                "source": "manual",
                "dismissal_reason": None,
                "match_tier": None,
                "salary": None,
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
                "is_sparse": False,
                "company_metadata": None,
                "location_metadata": None,
            }
        ]
        self._application_stats = {
            "total": 1,
            "active_count": 1,
            "offers_count": 0,
            "response_rate": 0.0,
            "avg_time_to_response_days": None,
            "status_counts": {"applied": 1},
            "weekly_velocity": [],
            "funnel": {
                "applied": 1,
                "screening": 0,
                "interviewing": 0,
                "offer": 0,
                "accepted": 0,
            },
            "outcome_breakdown": {},
            "source_breakdown": {"manual": 1},
            "top_companies": [],
        }
        self.list_calls = 0
        self.stats_calls = 0

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        return self._metadata.get(key, default)

    def set_metadata(self, key: str, value: str) -> None:
        self._metadata[key] = value

    def get_applications_filtered(
        self,
        *,
        application_statuses=None,
        search=None,
        sort="next_stage_date",
        order="asc",
        page=1,
        per_page=50,
    ):
        self.list_calls += 1
        return list(self._application_rows), len(self._application_rows)

    def get_application_stats(self) -> dict:
        self.stats_calls += 1
        return dict(self._application_stats)


def test_list_applications_reuses_cached_payload_until_fingerprint_changes():
    store = _FakeApplicationsStore()

    with patch.object(applications_router, "get_store", return_value=store):
        first = applications_router.list_applications(profile="default", status="applied", page=1, per_page=50)
        store._application_rows[0]["title"] = "Changed Title"
        second = applications_router.list_applications(profile="default", status="applied", page=1, per_page=50)

    assert first.jobs[0].title == "QA Lead"
    assert second.jobs[0].title == "QA Lead"
    assert store.list_calls == 1


def test_list_applications_cache_invalidates_after_status_change():
    store = _FakeApplicationsStore()

    with patch.object(applications_router, "get_store", return_value=store):
        first = applications_router.list_applications(profile="default", status="applied", page=1, per_page=50)
        store._application_rows[0]["application_status"] = "screening"
        store.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
        second = applications_router.list_applications(profile="default", status="applied", page=1, per_page=50)

    assert first.jobs[0].application_status == "applied"
    assert second.jobs[0].application_status == "screening"
    assert store.list_calls == 2


def test_get_application_stats_reuses_cached_payload_until_fingerprint_changes():
    store = _FakeApplicationsStore()

    with patch.object(applications_router, "get_store", return_value=store):
        first = applications_router.get_application_stats(profile="default")
        store._application_stats["total"] = 99
        second = applications_router.get_application_stats(profile="default")

    assert first.total == 1
    assert second.total == 1
    assert store.stats_calls == 1


def test_get_application_stats_cache_invalidates_after_status_change():
    store = _FakeApplicationsStore()

    with patch.object(applications_router, "get_store", return_value=store):
        first = applications_router.get_application_stats(profile="default")
        store._application_stats["total"] = 3
        store.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
        second = applications_router.get_application_stats(profile="default")

    assert first.total == 1
    assert second.total == 3
    assert store.stats_calls == 2
