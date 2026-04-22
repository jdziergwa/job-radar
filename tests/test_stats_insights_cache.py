import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from api.routers import stats as stats_router


class _FakeStore:
    def __init__(self, metadata: dict[str, str] | None = None, market_data: dict | None = None):
        self._metadata = metadata or {}
        self._market_data = market_data or {
            "total_scored": 6,
            "skip_reason_distribution": {},
            "country_distribution": [],
            "missing_skills": [],
            "apply_priority_counts": {},
            "salary_distribution": [],
        }

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        return self._metadata.get(key, default)

    def set_metadata(self, key: str, value: str) -> None:
        self._metadata[key] = value

    def get_market_intelligence(self, days: int = 30) -> dict:
        return self._market_data


pytestmark = [pytest.mark.anyio, pytest.mark.unit]


async def test_get_insights_reuses_recent_cache_when_pipeline_has_not_advanced():
    generated_at = (datetime.utcnow() - timedelta(days=1)).isoformat()
    store = _FakeStore(
        metadata={
            "insights_cache_default_30": json.dumps({
                "report": "cached report",
                "generated_at": generated_at,
            }),
            "last_pipeline_run_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
        }
    )

    with patch.object(stats_router, "get_store", return_value=store), patch.object(
        stats_router,
        "_generate_insights_report",
        new=AsyncMock(return_value="fresh report"),
    ) as generator:
        response = await stats_router.get_insights(profile="default", days=30, force=False)

    assert response.report == "cached report"
    assert response.cached is True
    generator.assert_not_awaited()


async def test_get_insights_returns_cached_report_without_regenerating_when_not_forced():
    generated_at = (datetime.utcnow() - timedelta(days=1)).isoformat()
    store = _FakeStore(
        metadata={
            "insights_cache_default_30": json.dumps({
                "report": "cached report",
                "generated_at": generated_at,
            }),
            "last_pipeline_run_at": datetime.utcnow().isoformat(),
        }
    )

    with patch.object(stats_router, "get_store", return_value=store), patch.object(
        stats_router,
        "_generate_insights_report",
        new=AsyncMock(return_value="fresh report"),
    ) as generator:
        response = await stats_router.get_insights(profile="default", days=30, force=False)

    assert response.report == "cached report"
    assert response.cached is True
    generator.assert_not_awaited()


async def test_get_insights_returns_empty_response_when_not_forced_and_cache_missing():
    store = _FakeStore()

    with patch.object(stats_router, "get_store", return_value=store), patch.object(
        stats_router,
        "_generate_insights_report",
        new=AsyncMock(return_value="fresh report"),
    ) as generator:
        response = await stats_router.get_insights(profile="default", days=30, force=False)

    assert response.report == ""
    assert response.generated_at == ""
    assert response.cached is False
    generator.assert_not_awaited()


async def test_get_insights_regenerates_when_forced():
    generated_at = (datetime.utcnow() - timedelta(days=1)).isoformat()
    store = _FakeStore(
        metadata={
            "insights_cache_default_30": json.dumps({
                "report": "cached report",
                "generated_at": generated_at,
            }),
        }
    )

    with patch.object(stats_router, "get_store", return_value=store), patch.object(
        stats_router,
        "_generate_insights_report",
        new=AsyncMock(return_value="fresh report"),
    ) as generator:
        response = await stats_router.get_insights(profile="default", days=30, force=True)

    assert response.report == "fresh report"
    assert response.cached is False
    generator.assert_awaited_once()
