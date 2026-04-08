from src.models import ScoredJob
from src.score_normalization import (
    build_normalization_audit,
    compute_weighted_fit_score,
    normalize_scored_job,
)


def _job(**overrides) -> ScoredJob:
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


def test_compute_weighted_fit_score_matches_documented_weights():
    weighted = compute_weighted_fit_score({
        "tech_stack_match": 92,
        "seniority_match": 90,
        "remote_location_fit": 70,
        "growth_potential": 88,
    })

    assert weighted == 85


def test_normalize_scored_job_caps_inflated_fit_score():
    raw = _job(
        fit_score=88,
        breakdown={
            "tech_stack_match": 92,
            "seniority_match": 90,
            "remote_location_fit": 70,
            "growth_potential": 88,
        },
        apply_priority="high",
        skip_reason="none",
    )

    normalized = normalize_scored_job(raw)

    assert normalized.fit_score == 85
    assert normalized.apply_priority == "high"
    assert normalized.skip_reason == "none"
    assert normalized.normalization_audit == {
        "raw_fit_score": 88,
        "weighted_fit_score": 85,
        "normalized_fit_score": 85,
        "raw_apply_priority": "high",
        "normalized_apply_priority": "high",
        "raw_skip_reason": "none",
        "normalized_skip_reason": "none",
        "changed_fields": ["fit_score"],
        "reason_codes": ["weighted_fit_cap"],
    }


def test_normalize_scored_job_preserves_downward_penalty():
    raw = _job(
        fit_score=50,
        breakdown={
            "tech_stack_match": 70,
            "seniority_match": 70,
            "remote_location_fit": 60,
            "growth_potential": 60,
        },
        apply_priority="medium",
        skip_reason="tech_gap",
    )

    normalized = normalize_scored_job(raw)

    assert normalized.fit_score == 50
    assert normalized.apply_priority == "low"
    assert normalized.skip_reason == "tech_gap"
    assert normalized.normalization_audit == {
        "raw_fit_score": 50,
        "weighted_fit_score": 66,
        "normalized_fit_score": 50,
        "raw_apply_priority": "medium",
        "normalized_apply_priority": "low",
        "raw_skip_reason": "tech_gap",
        "normalized_skip_reason": "tech_gap",
        "changed_fields": ["apply_priority"],
        "reason_codes": ["priority_rederived"],
    }


def test_normalize_scored_job_forces_skip_on_remote_hard_stop():
    raw = _job(
        fit_score=90,
        breakdown={
            "tech_stack_match": 95,
            "seniority_match": 90,
            "remote_location_fit": 20,
            "growth_potential": 90,
        },
        apply_priority="high",
        skip_reason="none",
    )

    normalized = normalize_scored_job(raw)

    assert normalized.fit_score == 39
    assert normalized.apply_priority == "skip"
    assert normalized.skip_reason == "location_timezone"
    assert normalized.normalization_audit == {
        "raw_fit_score": 90,
        "weighted_fit_score": 74,
        "normalized_fit_score": 39,
        "raw_apply_priority": "high",
        "normalized_apply_priority": "skip",
        "raw_skip_reason": "none",
        "normalized_skip_reason": "location_timezone",
        "changed_fields": ["fit_score", "apply_priority", "skip_reason"],
        "reason_codes": ["weighted_fit_cap", "remote_hard_stop", "priority_rederived", "skip_reason_normalized"],
    }


def test_build_normalization_audit_returns_empty_dict_when_nothing_changed():
    raw = _job(
        fit_score=85,
        breakdown={
            "tech_stack_match": 92,
            "seniority_match": 90,
            "remote_location_fit": 70,
            "growth_potential": 88,
        },
        apply_priority="high",
        skip_reason="none",
    )

    normalized = _job(
        fit_score=85,
        breakdown={
            "tech_stack_match": 92,
            "seniority_match": 90,
            "remote_location_fit": 70,
            "growth_potential": 88,
        },
        apply_priority="high",
        skip_reason="none",
    )

    assert build_normalization_audit(raw, normalized) == {}
