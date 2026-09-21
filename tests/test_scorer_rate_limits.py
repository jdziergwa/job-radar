import asyncio
import types
from dataclasses import replace

import pytest

import src.scorer as scorer
from src.claude import HAIKU_MODEL
from src.llm import LLMRateLimitError, set_adapter_override
from src.llm.anthropic_adapter import AnthropicAdapter
from src.models import CandidateJob, RawJob
from src.scorer import _ScoringRateLimiter, _rate_limit_wait_seconds, score_batch, score_job, score_jobs
from src.store import Store
from tests.fake_llm import FakeLLMAdapter


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
    return types.SimpleNamespace(content=[
        types.SimpleNamespace(type="thinking", thinking=""),
        types.SimpleNamespace(type="text", text=text),
    ], stop_reason="end_turn")


class _FakeMessages:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.requests: list[dict] = []

    async def create(self, *args, **kwargs):
        self.requests.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    """Stands in for AsyncAnthropic behind the real AnthropicAdapter."""

    def __init__(self, outcomes):
        self.messages = _FakeMessages(outcomes)

    async def close(self):
        pass


def test_rate_limit_wait_prefers_retry_after_header():
    wait = _rate_limit_wait_seconds(
        LLMRateLimitError(retry_after=1.5),
        1,
        is_batch=False,
    )

    assert wait == 1.5


def test_score_job_retries_after_rate_limit_and_succeeds(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(scorer.asyncio, "sleep", fake_sleep)

    client = FakeLLMAdapter([
        LLMRateLimitError(retry_after=3),
        ("""
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
        "Score jobs as JSON",
        rate_limiter=_ScoringRateLimiter(0),
    ))

    assert len(client.calls) == 2
    assert sleeps == pytest.approx([3.0], abs=0.01)
    assert result.fit_score == 78
    assert result.reasoning == "Strong backend fit."
    assert result.apply_priority in {"medium", "high"}


def test_score_job_returns_helpful_message_after_persistent_rate_limits(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(scorer.asyncio, "sleep", fake_sleep)

    client = FakeLLMAdapter([
        LLMRateLimitError(),
        LLMRateLimitError(),
        LLMRateLimitError(),
    ])

    result = asyncio.run(score_job(
        client,
        _candidate(),
        "Score jobs as JSON",
        rate_limiter=_ScoringRateLimiter(0),
    ))

    assert len(client.calls) == 3
    assert sleeps == pytest.approx([5.0, 10.0], abs=0.01)
    assert result.fit_score == 0
    assert result.reasoning == "Temporary scoring failure: Fake rate limits persisted after retries."
    assert result.apply_priority == "skip"


def test_structured_batch_maps_reordered_results_by_job_id():
    first = _candidate()
    second = replace(first, db_id=2, job_id="role-2")
    client = _FakeClient([_response('''{"jobs": [
        {"job_id": 2, "fit_score": 60, "reasoning": "Second job's own assessment"},
        {"job_id": 1, "fit_score": 80, "reasoning": "First job's own assessment"}
    ]}''')])

    results = asyncio.run(score_batch(AnthropicAdapter(client=client), [first, second], "", model=HAIKU_MODEL))

    assert [(r.db_id, r.reasoning) for r in results] == [
        (1, "First job's own assessment"), (2, "Second job's own assessment"),
    ]
    assert client.messages.requests[0]["output_config"]["format"]["schema"] == scorer._BATCH_SCORE_SCHEMA


@pytest.mark.parametrize("board_status", ["scored", "archived", "dismissed"])
def test_failed_rescore_keeps_previous_score_and_is_cleared_by_success(monkeypatch, tmp_path, board_status):
    store = Store(str(tmp_path / "jobs.db"))
    candidate = _candidate()
    store.upsert_jobs([RawJob(
        ats_platform=candidate.ats_platform, company_slug=candidate.company_slug,
        company_name=candidate.company_name, job_id=candidate.job_id, title=candidate.title,
        location=candidate.location, url=candidate.url, description=candidate.description,
        posted_at=candidate.posted_at, fetched_at=candidate.first_seen_at,
    )])
    job, = store.get_unscored()
    store.update_score(job.db_id, 85, "Previous score", {}, salary="$100k")
    assert store.get_job_by_id(job.db_id).status == "scored"
    store.update_status(job.db_id, board_status)
    truncated = _response('{"fit_score": 0, "reasoning": "Incomplete"}')
    truncated.stop_reason = "max_tokens"
    client = _FakeClient([truncated] * 3 + [_response('''{
        "fit_score": 82, "reasoning": "Updated score",
        "breakdown": {"tech_stack_match": 82, "seniority_match": 82, "remote_location_fit": 82, "growth_potential": 82}
    }''')])

    async def no_sleep(_):
        pass

    monkeypatch.setattr(scorer.asyncio, "sleep", no_sleep)
    set_adapter_override(AnthropicAdapter(client=client))
    try:
        result, = asyncio.run(score_jobs([job], "Profile", {}, store))

        truncated_error = "API_ERROR: Claude did not complete the response (max_tokens)"
        assert result.scoring_error == truncated_error
        saved = store.get_job_by_id(job.db_id)
        assert (saved.fit_score, saved.reasoning, saved.salary) == (85, "Previous score", "$100k")
        assert [candidate.db_id for candidate in store.get_jobs_for_rescore("failed_recent")] == [job.db_id]

        asyncio.run(score_jobs([job], "Profile", {}, store))
    finally:
        set_adapter_override(None)

    saved = store.get_job_by_id(job.db_id)
    assert saved.fit_score == 82
    assert saved.status == board_status
    assert not store.get_jobs_for_rescore("failed_recent")
    with store._connect() as conn:
        attempts = conn.execute("SELECT model, rubric_version, error FROM job_scoring_attempts ORDER BY id").fetchall()
    assert [attempt["model"] for attempt in attempts] == [HAIKU_MODEL, HAIKU_MODEL]
    assert attempts[0]["rubric_version"] == attempts[1]["rubric_version"]
    assert [attempt["error"] for attempt in attempts] == [truncated_error, None]
