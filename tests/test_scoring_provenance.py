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


async def test_returned_scored_jobs_carry_their_provenance(store, raw_job_factory):
    store.upsert_jobs([raw_job_factory()])
    adapter = FakeLLMAdapter([CONSISTENT_RESPONSE])
    set_adapter_override(adapter)
    try:
        scored = await score_jobs(
            store.get_unscored(), "profile", {"model": "fake-model-1", "min_request_interval_seconds": 0}, store,
        )
    finally:
        set_adapter_override(None)

    assert [job.provenance for job in scored] == [ScoringProvenance(adapter.name, "fake-model-1")]


async def test_score_single_carries_its_provenance(store, raw_job_factory):
    from src.scorer import LLMScorer

    store.upsert_jobs([raw_job_factory()])
    adapter = FakeLLMAdapter([CONSISTENT_RESPONSE])
    set_adapter_override(adapter)
    try:
        scored = await LLMScorer(model="fake-model-1").score_single(store.get_unscored()[0], "profile")
    finally:
        set_adapter_override(None)

    assert scored.provenance == ScoringProvenance(adapter.name, "fake-model-1")


def test_provenance_is_built_from_a_score_breakdown_in_one_place():
    assert ScoringProvenance.from_breakdown({"llm_provider": "gemini", "llm_model": "m"}) == ScoringProvenance("gemini", "m")
    assert ScoringProvenance.from_breakdown({"llm_provider": "gemini"}) is None
    assert ScoringProvenance.from_breakdown({}) is None
