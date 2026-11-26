import pytest

from src.llm import set_adapter_override
from src.models import CandidateJob
from src.scorer import score_jobs
from tests.fake_llm import FakeLLMAdapter

pytestmark = pytest.mark.anyio

RESPONSE = """{"fit_score": 70, "reasoning": "ok",
"breakdown": {"tech_stack_match": 70, "seniority_match": 70, "remote_location_fit": 70, "growth_potential": 70},
"key_matches": [], "red_flags": [], "apply_priority": "medium", "skip_reason": "none",
"missing_skills": [], "salary_info": {}, "is_sparse": false}"""


class _Store:
    def __init__(self):
        self.updates = []

    def get_metadata(self, key, default=None):
        return default

    def update_score(self, **kwargs):
        self.updates.append(kwargs)


def _job() -> CandidateJob:
    return CandidateJob(
        db_id=1, ats_platform="ashby", company_slug="x", company_name="X", job_id="1",
        title="Engineer", location="Remote", url="https://example.com/1",
        description="desc", posted_at=None, first_seen_at="2026-04-08T00:00:00",
    )


async def test_score_jobs_uses_resolver_adapter_and_profile_model(monkeypatch):
    fake = FakeLLMAdapter([RESPONSE])
    set_adapter_override(fake)
    try:
        store = _Store()
        results = await score_jobs(
            [_job()], "profile", {"model": "profile-model", "min_request_interval_seconds": 0}, store,
        )
    finally:
        set_adapter_override(None)

    assert results[0].fit_score == 70
    assert fake.calls[0]["model"] == "profile-model"
    assert fake.calls[0]["cache_system"] is True
    assert fake.calls[0]["json_output"] is True
    assert len(store.updates) == 1
