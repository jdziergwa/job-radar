"""An error retrying cannot fix (bad key, no credit, no access, unknown Model) stops scoring at once."""

import pytest

import src.scorer as scorer
from src.llm import LLMNonRetryableError, set_adapter_override
from src.scorer import score_jobs
from tests.fake_llm import FakeLLMAdapter

pytestmark = pytest.mark.anyio

NO_CREDIT = "402 RESOURCE_EXHAUSTED. Your prepayment credits are depleted."


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []

    async def fake_sleep(delay: float):
        recorded.append(delay)

    monkeypatch.setattr(scorer.asyncio, "sleep", fake_sleep)
    return recorded


@pytest.mark.parametrize("batch_size", [1, 2], ids=["single-job-calls", "batch-calls"])
async def test_error_retrying_cannot_fix_stops_scoring_after_one_call(
    no_ai_key, store, raw_job_factory, sleeps, batch_size,
):
    store.upsert_jobs([raw_job_factory(job_id=f"job-{i}", url=f"https://example.com/jobs/{i}") for i in range(5)])
    jobs = store.get_unscored()
    adapter = FakeLLMAdapter([LLMNonRetryableError(NO_CREDIT)])
    set_adapter_override(adapter)
    try:
        scored = await score_jobs(
            jobs, "Profile", {"min_request_interval_seconds": 0, "batch_size": batch_size}, store,
        )
    finally:
        set_adapter_override(None)

    assert len(adapter.calls) == 1
    assert sleeps == []
    assert [job.scoring_error for job in scored] == [f"API_ERROR: {NO_CREDIT}"] * len(jobs)
    assert sorted(job.db_id for job in store.get_jobs_for_rescore("failed_recent")) == sorted(job.db_id for job in jobs)
