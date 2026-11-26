import logging

import pytest

from src.llm import set_adapter_override
from src.log_file import excerpt
from src.models import CandidateJob
from src.scorer import score_jobs
from tests.fake_llm import FakeLLMAdapter

pytestmark = pytest.mark.anyio


def test_excerpt_keeps_short_text_whole_and_reports_length():
    assert excerpt("hello") == "'hello' (5 chars)"


def test_excerpt_cuts_long_text_and_reports_full_length():
    result = excerpt("a" * 1234, limit=10)

    assert result == "'aaaaaaaaaa'… (1234 chars)"


class _Store:
    def get_metadata(self, key, default=None):
        return default

    def update_score(self, **kwargs):
        pass

    def record_scoring_failure(self, *args, **kwargs):
        pass


def _job() -> CandidateJob:
    return CandidateJob(
        db_id=1, ats_platform="ashby", company_slug="x", company_name="X", job_id="1",
        title="Engineer", location="Remote", url="https://example.com/1",
        description="desc", posted_at=None, first_seen_at="2026-04-08T00:00:00",
    )


async def test_unparseable_scoring_response_is_logged_as_excerpt_with_length(caplog):
    long_response = "not json at all " + "CV-DETAIL " * 500
    set_adapter_override(FakeLLMAdapter([long_response] * 5))
    try:
        with caplog.at_level(logging.DEBUG):
            await score_jobs([_job()], "profile", {"min_request_interval_seconds": 0}, _Store())
    finally:
        set_adapter_override(None)

    assert f"({len(long_response)} chars)" in caplog.text
    assert long_response not in caplog.text
    assert "CV-DETAIL " * 100 not in caplog.text
