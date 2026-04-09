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


def build_normalization_audit(raw: ScoredJob, normalized: ScoredJob) -> dict[str, object]:
    """Build a structured audit payload when normalized values differ from raw output."""
    weighted_fit = compute_weighted_fit_score(raw.breakdown)
    changed_fields: list[str] = []
    reason_codes: list[str] = []

    if raw.fit_score != normalized.fit_score:
        changed_fields.append("fit_score")
        if normalized.fit_score == weighted_fit and raw.fit_score <= 0 and weighted_fit > 0:
            reason_codes.append("missing_raw_fit_backfilled")
        elif normalized.fit_score < raw.fit_score:
            reason_codes.append("weighted_fit_cap")

    if normalized.breakdown.get("remote_location_fit", 0) < 30 and normalized.fit_score < min(weighted_fit, _clamp_score(raw.fit_score)):
        if "remote_hard_stop" not in reason_codes:
            reason_codes.append("remote_hard_stop")

    if raw.apply_priority != normalized.apply_priority:
        changed_fields.append("apply_priority")
        reason_codes.append("priority_rederived")

    if raw.skip_reason != normalized.skip_reason:
        changed_fields.append("skip_reason")
        reason_codes.append("skip_reason_normalized")

    if not changed_fields:
        return {}

    return {
        "raw_fit_score": _clamp_score(raw.fit_score),
        "weighted_fit_score": weighted_fit,
        "normalized_fit_score": normalized.fit_score,
        "raw_apply_priority": raw.apply_priority,
        "normalized_apply_priority": normalized.apply_priority,
        "raw_skip_reason": raw.skip_reason,
        "normalized_skip_reason": normalized.skip_reason,
        "changed_fields": changed_fields,
        "reason_codes": reason_codes,
    }


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
    normalized = replace(
        result,
        fit_score=normalized_fit,
        breakdown=breakdown,
        apply_priority=normalized_priority,
        skip_reason=normalized_skip_reason,
    )

    return replace(
        normalized,
        normalization_audit=build_normalization_audit(result, normalized),
    )


def normalize_persisted_priority(
    fit_score: int | float | None,
    breakdown: dict[str, int] | None,
    apply_priority: str,
    skip_reason: str,
) -> tuple[str, str]:
    """Re-derive persisted priority/skip fields from normalized score data.

    This keeps legacy rows and UI/API reads consistent even if older
    score_breakdown JSON contains stale priority metadata.
    """
    breakdown = breakdown or {}
    remote_location_fit = _clamp_score(breakdown.get("remote_location_fit", 0))
    normalized_fit = _clamp_score(fit_score)
    normalized_priority = derive_apply_priority(normalized_fit, remote_location_fit)
    normalized_skip_reason = normalize_skip_reason(
        skip_reason,
        normalized_priority,
        remote_location_fit,
    )
    return normalized_priority, normalized_skip_reason
