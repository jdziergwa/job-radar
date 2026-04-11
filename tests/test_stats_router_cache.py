from datetime import datetime
from unittest.mock import patch

from api.routers import stats as stats_router


class _FakeAnalyticsStore:
    def __init__(self) -> None:
        self._metadata: dict[str, str] = {
            "last_pipeline_run_at": "2026-04-10T10:00:00",
        }
        self._stats = {
            "total_jobs": 10,
            "new_today": 2,
            "total_new_today": 3,
            "high_priority_today": 1,
            "new_this_week": 5,
            "last_pipeline_run_at": "2026-04-10T10:00:00",
            "scored": 6,
            "pending": 2,
            "applied": 1,
            "dismissed": 1,
            "closed": 0,
            "score_distribution": {"90-100": 1},
            "apply_priority_counts": {"high": 1, "medium": 2, "low": 1, "skip": 2},
        }
        self._trends = {
            "daily_counts": [],
            "pipeline_funnel": {
                "collected": 10,
                "passed_prefilter": 7,
                "high_priority": 2,
                "applied": 1,
            },
            "top_skills": [],
            "company_stats": [],
            "score_trend": [],
        }
        self._market = {
            "skip_reason_distribution": {"none": 4, "timezone": 2},
            "country_distribution": [],
            "missing_skills": [],
            "total_scored": 6,
            "apply_priority_counts": {"high": 2, "medium": 2, "skip": 2},
            "salary_distribution": [],
        }
        self.stats_calls = 0
        self.trends_calls = 0
        self.market_calls = 0

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        return self._metadata.get(key, default)

    def set_metadata(self, key: str, value: str) -> None:
        self._metadata[key] = value

    def get_stats(self) -> dict:
        self.stats_calls += 1
        return dict(self._stats)

    def get_trends(self, days: int = 30) -> dict:
        self.trends_calls += 1
        return {
            **self._trends,
            "pipeline_funnel": {
                **self._trends["pipeline_funnel"],
                "collected": self._trends["pipeline_funnel"]["collected"] + days,
            },
        }

    def get_market_intelligence(self, days: int = 30) -> dict:
        self.market_calls += 1
        return {
            **self._market,
            "total_scored": self._market["total_scored"] + days,
        }


def test_get_stats_reuses_cached_payload_until_fingerprint_changes():
    store = _FakeAnalyticsStore()

    with patch.object(stats_router, "get_store", return_value=store):
        first = stats_router.get_stats(profile="default")
        store._stats["total_jobs"] = 999
        second = stats_router.get_stats(profile="default")

    assert first.total_jobs == 10
    assert second.total_jobs == 10
    assert store.stats_calls == 1


def test_get_stats_cache_invalidates_after_status_change():
    store = _FakeAnalyticsStore()

    with patch.object(stats_router, "get_store", return_value=store):
        first = stats_router.get_stats(profile="default")
        store._stats["applied"] = 7
        store.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
        second = stats_router.get_stats(profile="default")

    assert first.applied == 1
    assert second.applied == 7
    assert store.stats_calls == 2


def test_get_trends_reuses_cached_payload_per_profile_and_days():
    store = _FakeAnalyticsStore()

    with patch.object(stats_router, "get_store", return_value=store):
        first = stats_router.get_trends(profile="default", days=7)
        second = stats_router.get_trends(profile="default", days=7)
        third = stats_router.get_trends(profile="default", days=30)

    assert first.pipeline_funnel.collected == second.pipeline_funnel.collected
    assert third.pipeline_funnel.collected != first.pipeline_funnel.collected
    assert store.trends_calls == 2


def test_get_market_intelligence_reuses_cached_payload():
    store = _FakeAnalyticsStore()

    with patch.object(stats_router, "get_store", return_value=store):
        first = stats_router.get_market_intelligence(profile="default", days=30)
        store._market["total_scored"] = 100
        second = stats_router.get_market_intelligence(profile="default", days=30)

    assert first.total_scored == 36
    assert second.total_scored == 36
    assert store.market_calls == 1
