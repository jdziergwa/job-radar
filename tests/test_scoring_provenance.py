import pytest

from src.llm import set_adapter_override
from src.models import ScoringProvenance
from src.scorer import score_jobs
from tests.fake_llm import FakeLLMAdapter

pytestmark = pytest.mark.anyio

CONSISTENT_RESPONSE = """{"fit_score": 70, "reasoning": "ok",
"breakdown": {"tech_stack_match": 70, "seniority_match": 70, "remote_location_fit": 70, "growth_potential": 70},
"key_matches": [], "red_flags": [], "apply_priority": "medium", "skip_reason": "none",
"missing_skills": [], "salary_info": {}, "is_sparse": false}"""


async def _score_all(store, adapter, model):
    set_adapter_override(adapter)
    try:
        await score_jobs(
            store.get_unscored(), "profile", {"model": model, "min_request_interval_seconds": 0}, store,
        )
    finally:
        set_adapter_override(None)


async def test_scored_job_records_provenance_even_when_normalization_changes_nothing(store, raw_job_factory):
    store.upsert_jobs([raw_job_factory()])
    db_id = store.get_unscored()[0].db_id
    adapter = FakeLLMAdapter([CONSISTENT_RESPONSE])

    await _score_all(store, adapter, "fake-model-1")

    stored = store.get_job_by_id(db_id)
    assert stored.normalization_audit == {}
    assert stored.provenance == ScoringProvenance(llm_provider=adapter.name, model="fake-model-1")
