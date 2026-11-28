import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from fastapi import HTTPException

from api.routers import stats as stats_router
from src.llm import LLMAPIError, LLMConfigError, LLMRateLimitError, set_adapter_override
from tests.fake_llm import FakeLLMAdapter


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


@pytest.fixture(autouse=True)
def _reset_adapter():
    yield
    set_adapter_override(None)


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

    fake = FakeLLMAdapter(["fresh report"])
    set_adapter_override(fake)

    with patch.object(stats_router, "get_store", return_value=store):
        response = await stats_router.get_insights(profile="default", days=30, force=False)

    assert response.report == "cached report"
    assert response.cached is True
    assert fake.calls == []


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

    fake = FakeLLMAdapter(["fresh report"])
    set_adapter_override(fake)

    with patch.object(stats_router, "get_store", return_value=store):
        response = await stats_router.get_insights(profile="default", days=30, force=False)

    assert response.report == "cached report"
    assert response.cached is True
    assert fake.calls == []


async def test_get_insights_returns_empty_response_when_not_forced_and_cache_missing():
    store = _FakeStore()

    fake = FakeLLMAdapter(["fresh report"])
    set_adapter_override(fake)

    with patch.object(stats_router, "get_store", return_value=store):
        response = await stats_router.get_insights(profile="default", days=30, force=False)

    assert response.report == ""
    assert response.generated_at == ""
    assert response.cached is False
    assert fake.calls == []


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

    fake = FakeLLMAdapter(["fresh report"])
    set_adapter_override(fake)

    with patch.object(stats_router, "get_store", return_value=store):
        response = await stats_router.get_insights(profile="default", days=30, force=True)

    assert response.report == "fresh report"
    assert response.cached is False
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "fake-model"


async def test_forced_insights_without_api_key_is_ai_not_configured(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    store = _FakeStore()

    with patch.object(stats_router, "get_store", return_value=store):
        with pytest.raises(HTTPException) as exc:
            await stats_router.get_insights(profile="default", days=30, force=True)

    assert exc.value.status_code == 503
    assert "AI not configured" in exc.value.detail


@pytest.mark.parametrize("error,fragment", [
    (LLMRateLimitError(), "Fake Rate Limit"),
    (LLMAPIError("boom"), "Fake API Error"),
])
async def test_forced_insights_maps_llm_errors_to_502(error, fragment):
    set_adapter_override(FakeLLMAdapter([error]))
    store = _FakeStore()

    with patch.object(stats_router, "get_store", return_value=store):
        with pytest.raises(HTTPException) as exc:
            await stats_router.get_insights(profile="default", days=30, force=True)

    assert exc.value.status_code == 502
    assert fragment in exc.value.detail
    assert store.get_metadata("insights_cache_default_30") is None


async def test_forced_insights_missing_llm_provider_sdk_is_ai_not_configured(monkeypatch):
    def _no_sdk():
        raise LLMConfigError("The Gemini SDK isn't installed. Install it with: pip install google-genai")

    monkeypatch.setattr(stats_router, "get_adapter", _no_sdk)

    with patch.object(stats_router, "get_store", return_value=_FakeStore()):
        with pytest.raises(HTTPException) as exc:
            await stats_router.get_insights(profile="default", days=30, force=True)

    assert exc.value.status_code == 503
    assert exc.value.detail == "AI not configured: The Gemini SDK isn't installed. Install it with: pip install google-genai"
