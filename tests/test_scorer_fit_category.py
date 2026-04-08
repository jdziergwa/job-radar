import sys
import types


if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class AsyncAnthropic:  # pragma: no cover - stub for import only
        pass

    anthropic.AsyncAnthropic = AsyncAnthropic
    anthropic.Anthropic = AsyncAnthropic
    anthropic.RateLimitError = Exception
    anthropic.APIError = Exception
    sys.modules["anthropic"] = anthropic

from src.models import CandidateJob, ScoredJob
from src.scorer import _derive_fit_category


def _candidate(title: str, company_metadata: dict | None = None) -> CandidateJob:
    return CandidateJob(
        db_id=1,
        ats_platform="test",
        company_slug="example",
        company_name="ExampleCo",
        job_id="1",
        title=title,
        location="Remote",
        company_metadata=company_metadata or {},
        url="https://example.com/jobs/1",
        description="Example description",
        posted_at=None,
        first_seen_at="2026-04-08T00:00:00",
    )


def _result(**overrides) -> ScoredJob:
    base = ScoredJob(
        db_id=1,
        ats_platform="test",
        company_slug="example",
        company_name="ExampleCo",
        job_id="1",
        title="Example Role",
        location="Remote",
        url="https://example.com/jobs/1",
        description="Example description",
        posted_at=None,
        first_seen_at="2026-04-08T00:00:00",
        fit_score=0,
        reasoning="Example reasoning",
        breakdown={
            "tech_stack_match": 0,
            "seniority_match": 0,
            "remote_location_fit": 0,
            "growth_potential": 0,
        },
        apply_priority="skip",
        skip_reason="none",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _profile_config() -> dict:
    return {
        "scoring_context": {
            "role_targets": {
                "core": ["Senior Backend Engineer"],
                "adjacent": ["Staff Platform Engineer"],
                "seniority_preferences": ["senior", "staff"],
            },
            "company_preferences": {
                "preferred_signals": ["strong product company", "high engineering reputation"],
                "allow_lower_seniority_if_company_matches": True,
            },
            "decision_rules": {
                "adjacent_roles": {
                    "enabled": True,
                    "requires_bridge_evidence": True,
                    "prefer_core_when_equally_viable": False,
                    "portfolio_counts_as_bridge_evidence": True,
                },
                "lower_seniority_roles": {
                    "enabled": True,
                    "require_unusually_strong_scope": True,
                },
                "company_quality": {
                    "enabled": True,
                    "preferred_signals": ["strong product company", "high engineering reputation"],
                    "allow_lower_seniority_exception": True,
                },
            },
        }
    }


def test_derive_fit_category_marks_direct_core_match():
    fit_category = _derive_fit_category(
        _candidate("Senior Backend Engineer"),
        _result(
            title="Senior Backend Engineer",
            fit_score=84,
            apply_priority="high",
            breakdown={
                "tech_stack_match": 88,
                "seniority_match": 86,
                "remote_location_fit": 80,
                "growth_potential": 82,
            },
        ),
        _profile_config(),
    )

    assert fit_category == "core_fit"


def test_derive_fit_category_marks_adjacent_stretch_role():
    fit_category = _derive_fit_category(
        _candidate("Platform Engineer"),
        _result(
            title="Platform Engineer",
            fit_score=71,
            apply_priority="medium",
            breakdown={
                "tech_stack_match": 67,
                "seniority_match": 72,
                "remote_location_fit": 80,
                "growth_potential": 84,
            },
        ),
        _profile_config(),
    )

    assert fit_category == "adjacent_stretch"


def test_derive_fit_category_marks_lower_seniority_role_as_conditional():
    fit_category = _derive_fit_category(
        _candidate("Mid Backend Engineer"),
        _result(
            title="Mid Backend Engineer",
            fit_score=61,
            apply_priority="medium",
            breakdown={
                "tech_stack_match": 76,
                "seniority_match": 58,
                "remote_location_fit": 82,
                "growth_potential": 86,
            },
        ),
        _profile_config(),
    )

    assert fit_category == "conditional_fit"


def test_derive_fit_category_marks_strategic_exception_when_company_signal_matches():
    fit_category = _derive_fit_category(
        _candidate(
            "Mid Backend Engineer",
            company_metadata={
                "quality_signals": ["strong product company"],
                "source": "companies_yaml",
            },
        ),
        _result(
            title="Mid Backend Engineer",
            fit_score=64,
            apply_priority="medium",
            breakdown={
                "tech_stack_match": 71,
                "seniority_match": 55,
                "remote_location_fit": 82,
                "growth_potential": 76,
            },
        ),
        _profile_config(),
    )

    assert fit_category == "strategic_exception"
