"""Helpers for normalizing scorer output before persistence."""

from __future__ import annotations

from dataclasses import replace

from src.models import ScoredJob

DIMENSION_WEIGHTS = {
    "tech_stack_match": 0.30,
    "seniority_match": 0.25,
    "remote_location_fit": 0.25,
    "growth_potential": 0.20,
}

VALID_PRIORITIES = {"high", "medium", "low", "skip"}
VALID_SKIP_REASONS = {
    "location_onsite",
    "location_timezone",
    "tech_gap",
    "seniority_mismatch",
    "growth_mismatch",
    "none",
}


def _clamp_score(value: int | float | None) -> int:
    try:
        return max(0, min(100, int(round(float(value or 0)))))
    except (TypeError, ValueError):
        return 0


def compute_weighted_fit_score(breakdown: dict[str, int]) -> int:
    """Compute the documented weighted score from dimension breakdown."""
    total = 0.0
    for key, weight in DIMENSION_WEIGHTS.items():
        total += _clamp_score(breakdown.get(key, 0)) * weight
    return _clamp_score(total)


def derive_apply_priority(fit_score: int, remote_location_fit: int) -> str:
    """Derive apply priority from normalized fit score and hard-stop rules."""
    if remote_location_fit < 30 or fit_score < 40:
        return "skip"
    if fit_score >= 80:
        return "high"
    if fit_score >= 60:
        return "medium"
    return "low"


def normalize_skip_reason(skip_reason: str, apply_priority: str, remote_location_fit: int) -> str:
    """Normalize skip reason to a valid value that matches hard-stop behavior."""
    normalized = skip_reason if skip_reason in VALID_SKIP_REASONS else "none"
    if apply_priority in {"high", "medium"}:
        return "none"
    if remote_location_fit < 30 and normalized == "none":
        return "location_timezone"
    return normalized


def normalize_scored_job(result: ScoredJob) -> ScoredJob:
    """Normalize a scored job so persisted score fields cannot contradict each other."""
    breakdown = {key: _clamp_score(val) for key, val in result.breakdown.items()}
    weighted_fit = compute_weighted_fit_score(breakdown)
    raw_fit = _clamp_score(result.fit_score)
    remote_location_fit = breakdown.get("remote_location_fit", 0)

    if raw_fit <= 0 and weighted_fit > 0:
        normalized_fit = weighted_fit
    else:
        normalized_fit = min(weighted_fit, raw_fit)

    # Remote hard-stop should not leave a high-looking fit score in storage.
    if remote_location_fit < 30:
        normalized_fit = min(normalized_fit, 39)

    normalized_priority = derive_apply_priority(normalized_fit, remote_location_fit)
    normalized_skip_reason = normalize_skip_reason(
        result.skip_reason,
        normalized_priority,
        remote_location_fit,
    )

    return replace(
        result,
        fit_score=normalized_fit,
        breakdown=breakdown,
        apply_priority=normalized_priority,
        skip_reason=normalized_skip_reason,
    )
