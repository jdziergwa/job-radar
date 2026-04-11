import asyncio
import types

import pytest

from src.models import CandidateJob
from src.scorer import _ScoringRateLimiter, _rate_limit_wait_seconds, score_job
import src.scorer as scorer


def _candidate() -> CandidateJob:
    return CandidateJob(
        db_id=1,
        ats_platform="ashby",
        company_slug="example",
        company_name="ExampleCo",
        job_id="role-1",
        title="Platform Engineer",
        location="Remote",
        url="https://example.com/jobs/1",
        description="Example description",
        posted_at=None,
        first_seen_at="2026-04-08T00:00:00",
    )


def _response(text: str):
    return types.SimpleNamespace(content=[types.SimpleNamespace(text=text)])


class _FakeRateLimitError(Exception):
    def __init__(self, headers: dict[str, str] | None = None):
        super().__init__("rate limited")
        self.response = types.SimpleNamespace(headers=headers or {})


class _FakeMessages:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    async def create(self, *args, **kwargs):
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, outcomes):
        self.messages = _FakeMessages(outcomes)


def test_rate_limit_wait_prefers_retry_after_header():
    wait = _rate_limit_wait_seconds(
        _FakeRateLimitError({"retry-after-ms": "1500"}),
        1,
        is_batch=False,
    )

    assert wait == 1.5


def test_score_job_retries_after_rate_limit_and_succeeds(monkeypatch):
    monkeypatch.setattr(scorer.anthropic, "RateLimitError", _FakeRateLimitError)

    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(scorer.asyncio, "sleep", fake_sleep)

    client = _FakeClient([
        _FakeRateLimitError({"retry-after": "3"}),
        _response("""
        {
          "fit_score": 78,
          "reasoning": "Strong backend fit.",
          "breakdown": {
            "tech_stack_match": 80,
            "seniority_match": 75,
            "remote_location_fit": 76,
            "growth_potential": 81
          },
          "key_matches": [],
          "red_flags": [],
          "apply_priority": "high",
          "skip_reason": "none",
          "missing_skills": [],
          "salary_info": {},
          "is_sparse": false
        }
        """),
    ])

    result = asyncio.run(score_job(
        client,
        _candidate(),
        [{"type": "text", "text": "Score jobs as JSON"}],
        rate_limiter=_ScoringRateLimiter(0),
    ))

    assert client.messages.calls == 2
    assert sleeps == pytest.approx([3.0], abs=0.01)
    assert result.fit_score == 78
    assert result.reasoning == "Strong backend fit."
    assert result.apply_priority in {"medium", "high"}


def test_score_job_returns_helpful_message_after_persistent_rate_limits(monkeypatch):
    monkeypatch.setattr(scorer.anthropic, "RateLimitError", _FakeRateLimitError)

    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(scorer.asyncio, "sleep", fake_sleep)

    client = _FakeClient([
        _FakeRateLimitError(),
        _FakeRateLimitError(),
        _FakeRateLimitError(),
    ])

    result = asyncio.run(score_job(
        client,
        _candidate(),
        [{"type": "text", "text": "Score jobs as JSON"}],
        rate_limiter=_ScoringRateLimiter(0),
    ))

    assert client.messages.calls == 3
    assert sleeps == pytest.approx([5.0, 10.0], abs=0.01)
    assert result.fit_score == 0
    assert result.reasoning == "Temporary scoring failure: Anthropic rate limits persisted after retries."
    assert result.apply_priority == "skip"
