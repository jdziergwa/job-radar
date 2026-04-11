"""LLM scoring via Claude API — sends candidate jobs for fit assessment.

Uses anthropic SDK with prompt caching. System prompt (scoring instructions +
profile doc) is cached; user message (job posting) changes per call.
"""

from __future__ import annotations

import asyncio
import email.utils
import json
import logging
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable, Optional, Callable

import anthropic
from anthropic import AsyncAnthropic

from src.models import CandidateJob, ScoredJob
from src.score_normalization import compute_weighted_fit_score, normalize_scored_job
from src.store import Store

logger = logging.getLogger(__name__)

# Delay between API calls to be respectful
CALL_DELAY = 0.5  # seconds
MAX_RETRIES = 3


class _ScoringRateLimiter:
    """Coordinate request pacing and shared cooldowns across concurrent scorers."""

    def __init__(self, min_interval_seconds: float = CALL_DELAY):
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._next_request_at = 0.0
        self._cooldown_until = 0.0
        self._lock = asyncio.Lock()

    async def wait_for_slot(self) -> None:
        delay = 0.0
        async with self._lock:
            now = asyncio.get_running_loop().time()
            ready_at = max(now, self._next_request_at, self._cooldown_until)
            self._next_request_at = ready_at + self.min_interval_seconds if self.min_interval_seconds > 0 else ready_at
            delay = ready_at - now

        if delay > 0:
            await asyncio.sleep(delay)

    async def apply_cooldown(self, seconds: float) -> None:
        if seconds <= 0:
            return

        async with self._lock:
            now = asyncio.get_running_loop().time()
            cooldown_until = now + seconds
            if cooldown_until > self._cooldown_until:
                self._cooldown_until = cooldown_until
            if self._next_request_at < self._cooldown_until:
                self._next_request_at = self._cooldown_until


def _parse_retry_after_seconds(headers: Any) -> float | None:
    """Best-effort parsing of retry-after headers from Anthropic responses."""
    if headers is None:
        return None

    retry_after_ms = headers.get("retry-after-ms")
    try:
        if retry_after_ms is not None:
            seconds = float(retry_after_ms) / 1000
            if seconds > 0:
                return seconds
    except (TypeError, ValueError):
        pass

    retry_after = headers.get("retry-after")
    try:
        if retry_after is not None:
            seconds = float(retry_after)
            if seconds > 0:
                return seconds
    except (TypeError, ValueError):
        pass

    if retry_after:
        try:
            retry_dt = email.utils.parsedate_to_datetime(retry_after)
            if retry_dt is None:
                return None
            if retry_dt.tzinfo is None:
                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
            seconds = (retry_dt - datetime.now(timezone.utc)).total_seconds()
            if seconds > 0:
                return seconds
        except (TypeError, ValueError, IndexError):
            return None

    return None


def _rate_limit_wait_seconds(error: Exception, attempt: int, *, is_batch: bool) -> float:
    """Prefer server-provided retry headers, otherwise back off conservatively."""
    response = getattr(error, "response", None)
    retry_after = _parse_retry_after_seconds(getattr(response, "headers", None))
    if retry_after is not None:
        return min(retry_after, 60.0)

    base_wait = 10.0 if is_batch else 5.0
    return min(base_wait * (2 ** (attempt - 1)), 60.0)


def _log_normalization(raw: ScoredJob, normalized: ScoredJob) -> None:
    """Log score normalization adjustments when persisted values differ from raw LLM output."""
    audit = normalized.normalization_audit or {}
    if not audit:
        return

    logger.info(
        "Normalized score for %s @ %s: raw_fit=%d weighted=%d normalized_fit=%d raw_priority=%s normalized_priority=%s raw_skip=%s normalized_skip=%s reasons=%s",
        raw.title,
        raw.company_name,
        audit.get("raw_fit_score", raw.fit_score),
        audit.get("weighted_fit_score", compute_weighted_fit_score(raw.breakdown)),
        audit.get("normalized_fit_score", normalized.fit_score),
        audit.get("raw_apply_priority", raw.apply_priority),
        audit.get("normalized_apply_priority", normalized.apply_priority),
        audit.get("raw_skip_reason", raw.skip_reason),
        audit.get("normalized_skip_reason", normalized.skip_reason),
        ",".join(str(code) for code in audit.get("reason_codes", [])) or "none",
    )


# Resolve paths relative to this file, not cwd
_SRC_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SRC_DIR.parent


def load_prompt_structure() -> str:
    """Load the fixed structural template from src/prompts/scoring_structure.md."""
    path = _SRC_DIR / "prompts" / "scoring_structure.md"
    if not path.exists():
        logger.error("Structural prompt template not found at %s", path)
        return "{scoring_philosophy}"  # Minimum viable fallback
    return path.read_text(encoding="utf-8").strip()


def load_scoring_philosophy(profile_dir: Path | None = None) -> str:
    """Load the scoring philosophy section for the given profile.

    Checks for:
    1. Per-profile scoring_philosophy.md
    2. profiles/example/scoring_philosophy.md (universal fallback)
    """
    if profile_dir is not None:
        philosophy_path = profile_dir / "scoring_philosophy.md"
        if philosophy_path.exists():
            return philosophy_path.read_text(encoding="utf-8").strip()

    # Universal fallback: the example profile philosophy
    fallback_path = _PROJECT_ROOT / "profiles" / "example" / "scoring_philosophy.md"
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8").strip()

    logger.warning("No scoring philosophy found in profile or example — using empty philosophy")
    return ""


def _build_system_prompt(scoring_instructions: str, profile_doc: str, profile_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Build the system message with cache_control for prompt caching."""
    import yaml

    # Send only the scoring-relevant subset of config to avoid token-heavy
    # prefilter regex noise in the cached system prompt.
    preferences_block = ""
    if profile_config:
        prompt_config = _build_prompt_profile_config(profile_config)
        if prompt_config:
            formatted_config = yaml.dump(prompt_config, sort_keys=False, default_flow_style=False)
            preferences_block = f"\n\nCANDIDATE PREFERENCES (from search_config.yaml):\n\n{formatted_config}"

    return [{
        "type": "text",
        "text": f"{scoring_instructions}{preferences_block}\n\nCANDIDATE PROFILE (from profile_doc.md):\n\n{profile_doc}",
        "cache_control": {"type": "ephemeral"},
    }]


def _build_prompt_profile_config(profile_config: dict[str, Any]) -> dict[str, Any]:
    """Keep only scoring-relevant config in the prompt context."""
    curated: dict[str, Any] = {}

    scoring_context = profile_config.get("scoring_context")
    if isinstance(scoring_context, dict) and scoring_context:
        curated["scoring_context"] = scoring_context

    # Backward-compatible fallback for profiles that do not yet provide
    # structured scoring_context. Keep only the most relevant keyword signals.
    if "scoring_context" not in curated:
        keywords = profile_config.get("keywords")
        if isinstance(keywords, dict) and keywords:
            compact_keywords: dict[str, Any] = {}

            title_patterns = keywords.get("title_patterns")
            if isinstance(title_patterns, dict):
                compact_titles: dict[str, list[str]] = {}
                for key in ("high_confidence", "broad"):
                    values = _ensure_string_list(title_patterns.get(key))
                    if values:
                        compact_titles[key] = values
                if compact_titles:
                    compact_keywords["title_patterns"] = compact_titles

            exclusions = _ensure_string_list(keywords.get("exclusions"))
            if exclusions:
                compact_keywords["exclusions"] = exclusions

            if compact_keywords:
                curated["keywords"] = compact_keywords

    return curated


def _summarize_location_metadata(location_metadata: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}

    workplace_type = location_metadata.get("workplace_type")
    if isinstance(workplace_type, str) and workplace_type.strip():
        summary["workplace_type"] = workplace_type.strip()

    employment_type = location_metadata.get("employment_type")
    if isinstance(employment_type, str) and employment_type.strip():
        summary["employment_type"] = employment_type.strip()

    derived_signals = _ensure_string_list(location_metadata.get("derived_geographic_signals"))
    if derived_signals:
        summary["derived_geographic_signals"] = derived_signals

    location_fragments = _ensure_string_list(location_metadata.get("location_fragments"))
    if location_fragments and "derived_geographic_signals" not in summary:
        summary["location_fragments"] = location_fragments

    return summary


def _format_location_context(location_metadata: dict[str, object]) -> str:
    if not location_metadata:
        return ""

    import yaml

    prompt_metadata = _summarize_location_metadata(location_metadata)
    formatted = yaml.dump(prompt_metadata or location_metadata, sort_keys=False, default_flow_style=False).strip()
    if not formatted:
        return ""
    return f"\nLocation Context:\n{formatted}\n"


def _summarize_company_metadata(company_metadata: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}
    quality_signals = _ensure_string_list(company_metadata.get("quality_signals"))
    if quality_signals:
        summary["quality_signals"] = quality_signals
    return summary


def _format_company_context(company_metadata: dict[str, object]) -> str:
    if not company_metadata:
        return ""

    import yaml

    prompt_metadata = _summarize_company_metadata(company_metadata)
    formatted = yaml.dump(prompt_metadata or company_metadata, sort_keys=False, default_flow_style=False).strip()
    if not formatted:
        return ""
    return f"\nCompany Context:\n{formatted}\n"


_SENIORITY_PREFIXES = {
    "junior", "jr", "jr.", "mid", "middle", "senior", "sr", "sr.",
    "lead", "staff", "principal", "head",
}
_LOWER_SENIORITY_MARKERS = {"junior", "jr", "jr.", "mid", "middle", "associate"}


def _normalize_phrase(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return " ".join(cleaned.split())


def _role_match_phrases(role: str) -> list[str]:
    normalized = _normalize_phrase(role)
    if not normalized:
        return []

    phrases = [normalized]
    without_parens = _normalize_phrase(re.sub(r"\([^)]*\)", "", role or ""))
    if without_parens:
        phrases.append(without_parens)

    tokens = normalized.split()
    while tokens and tokens[0] in _SENIORITY_PREFIXES:
        tokens = tokens[1:]
    if tokens:
        phrases.append(" ".join(tokens))

    return list(dict.fromkeys(phrase for phrase in phrases if phrase))


def _title_matches_role_target(title: str, role: str) -> bool:
    normalized_title = _normalize_phrase(title)
    return any(phrase in normalized_title for phrase in _role_match_phrases(role))


def _title_looks_lower_seniority(title: str) -> bool:
    tokens = set(_normalize_phrase(title).split())
    return bool(tokens & _LOWER_SENIORITY_MARKERS)


def _ensure_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _company_has_preferred_quality_signal(
    company_metadata: dict[str, object],
    preferred_signals: list[str],
) -> bool:
    company_signals = {value.lower() for value in _ensure_string_list(company_metadata.get("quality_signals"))}
    preferred = {value.lower() for value in preferred_signals}
    return bool(company_signals & preferred)


def _derive_fit_category(
    job: CandidateJob,
    result: ScoredJob,
    profile_config: dict[str, Any] | None,
) -> str:
    """Classify the scored result using structured wizard intent."""
    if result.apply_priority == "skip":
        return ""

    scoring_context = (profile_config or {}).get("scoring_context", {})
    if not isinstance(scoring_context, dict):
        return ""

    role_targets = scoring_context.get("role_targets", {}) if isinstance(scoring_context.get("role_targets", {}), dict) else {}
    decision_rules = scoring_context.get("decision_rules", {}) if isinstance(scoring_context.get("decision_rules", {}), dict) else {}
    company_preferences = scoring_context.get("company_preferences", {}) if isinstance(scoring_context.get("company_preferences", {}), dict) else {}

    core_roles = _ensure_string_list(role_targets.get("core"))
    adjacent_roles = _ensure_string_list(role_targets.get("adjacent"))
    seniority_preferences = {value.lower() for value in _ensure_string_list(role_targets.get("seniority_preferences"))}
    breakdown = result.breakdown or {}
    preferred_company_signals = _ensure_string_list(company_preferences.get("preferred_signals"))

    title = job.title or result.title
    growth = int(breakdown.get("growth_potential", 0) or 0)
    tech = int(breakdown.get("tech_stack_match", 0) or 0)
    seniority = int(breakdown.get("seniority_match", 0) or 0)
    company_quality_rules = decision_rules.get("company_quality", {})

    if (
        isinstance(company_quality_rules, dict)
        and company_quality_rules.get("allow_lower_seniority_exception")
        and _title_looks_lower_seniority(title)
        and seniority < 70
        and tech >= 55
        and growth >= 65
        and result.apply_priority in {"low", "medium"}
        and _company_has_preferred_quality_signal(job.company_metadata, preferred_company_signals)
    ):
        return "strategic_exception"

    lower_seniority_rules = decision_rules.get("lower_seniority_roles", {})
    if (
        isinstance(lower_seniority_rules, dict)
        and lower_seniority_rules.get("enabled")
        and lower_seniority_rules.get("require_unusually_strong_scope")
        and seniority_preferences & {"senior", "lead", "staff", "principal"}
        and _title_looks_lower_seniority(title)
        and seniority < 70
        and growth >= 75
        and result.apply_priority in {"low", "medium"}
    ):
        return "conditional_fit"

    adjacent_rules = decision_rules.get("adjacent_roles", {})
    if (
        isinstance(adjacent_rules, dict)
        and adjacent_rules.get("enabled")
        and any(_title_matches_role_target(title, role) for role in adjacent_roles)
        and growth >= 65
        and tech >= 45
        and result.apply_priority in {"low", "medium", "high"}
    ):
        return "adjacent_stretch"

    if (
        any(_title_matches_role_target(title, role) for role in core_roles)
        and result.apply_priority in {"medium", "high"}
    ):
        return "core_fit"

    return ""


def _build_user_message(job: CandidateJob, max_desc_chars: int = 20000) -> str:
    """Build the user message containing the job posting."""
    from src.providers.utils import strip_html
    
    raw_desc = job.description or "(No description available)"
    # Strip HTML to save tokens and avoid noise for the LLM
    description = strip_html(raw_desc)[:max_desc_chars]

    return f"""<job>
Title: {job.title}
Company: {job.company_name}
Location: {job.location}
Salary (extracted): {job.salary}
URL: {job.url}

Description:
{description}
</job>

{_format_company_context(job.company_metadata)}
{_format_location_context(job.location_metadata)}

Score this job's fit for the candidate."""


def _parse_numeric_score(val: Any) -> int:
    """Safely convert any numeric-like value to an integer (0-100)."""
    if val is None:
        return 0
    try:
        if isinstance(val, str):
            # Handle "90%", "85/100", etc.
            clean_val = "".join(c for c in val if c.isdigit() or c == ".")
            return max(0, min(100, int(float(clean_val)))) if clean_val else 0
        return max(0, min(100, int(float(val))))
    except (ValueError, TypeError):
        return 0


def _get_score_from_dict(data: dict) -> int:
    """Extract overall fit_score from dict, handling common LLM key variations."""
    variants = ["fit_score", "score", "fitScore", "overall_fit_score", "fit score", "overall fit score"]
    lower_data = {k.lower(): v for k, v in data.items()}
    
    for var in variants:
        if var in lower_data:
            return _parse_numeric_score(lower_data[var])
            
    return 0


def _get_breakdown_from_dict(data: dict) -> dict[str, int]:
    """Extract breakdown dimensions, handling both nested and top-level keys."""
    # LLMs sometimes nest everything under 'breakdown' or 'dimensions'
    raw_breakdown = data.get("breakdown", {})
    if not isinstance(raw_breakdown, dict):
        raw_breakdown = {}
        
    # Also check if there's a nested 'dimensions' inside 'breakdown'
    inner_dimensions = raw_breakdown.get("dimensions", {})
    if not isinstance(inner_dimensions, dict):
        inner_dimensions = {}

    dimensions = ["tech_stack_match", "seniority_match", "remote_location_fit", "growth_potential"]
    result = {}
    
    # Pre-process all candidates for lookups
    lookups = [
        inner_dimensions,
        raw_breakdown,
        data  # Top level
    ]
    
    lower_lookups = [{k.lower(): v for k, v in d.items()} for d in lookups]
    
    for dim in dimensions:
        val = None
        for lookup in lower_lookups:
            # 1. Try exact match
            val = lookup.get(dim)
            if val is not None:
                break
            
            # 2. Try short version (e.g. "tech_stack" for "tech_stack_match")
            short_dim = dim.split("_match")[0].split("_fit")[0].split("_potential")[0]
            val = lookup.get(short_dim)
            if val is not None:
                break
                
        result[dim] = _parse_numeric_score(val)
        
    return result


def _extract_metadata(data: dict) -> dict[str, Any]:
    """Extract lists and priority from JSON, checking both top-level and breakdown."""
    breakdown = data.get("breakdown", {})
    if not isinstance(breakdown, dict):
        breakdown = {}
        
    def get_field(key: str, default: Any) -> Any:
        # Priority 1: Top-level
        val = data.get(key)
        if val is not None:
            return val
        # Priority 2: Inside breakdown
        return breakdown.get(key, default)

    VALID_SKIP_REASONS = {
        "location_onsite", "location_timezone", "tech_gap",
        "seniority_mismatch", "growth_mismatch", "none"
    }
    raw_skip = get_field("skip_reason", "none")
    skip_reason = raw_skip if isinstance(raw_skip, str) and raw_skip in VALID_SKIP_REASONS else "none"

    missing_skills = get_field("missing_skills", [])
    if not isinstance(missing_skills, list):
        missing_skills = []

    salary_info = get_field("salary_info", {})
    if not isinstance(salary_info, dict):
        salary_info = {}

    # Flexible extraction: check nested first, then top-level fallbacks
    salary_str = salary_info.get("salary") or get_field("salary", None)
    s_min = salary_info.get("min") or get_field("salary_min", None)
    s_max = salary_info.get("max") or get_field("salary_max", None)
    s_cur = salary_info.get("currency") or get_field("salary_currency", None)

    return {
        "key_matches": get_field("key_matches", []),
        "red_flags": get_field("red_flags", []),
        "apply_priority": get_field("apply_priority", "skip"),
        "skip_reason": skip_reason,
        "missing_skills": missing_skills,
        "salary": salary_str,
        "salary_min": _parse_numeric_score(s_min) if s_min is not None else None,
        "salary_max": _parse_numeric_score(s_max) if s_max is not None else None,
        "salary_currency": str(s_cur) if s_cur else None,
        "is_sparse": bool(get_field("is_sparse", False)),
    }


def _extract_json(text: str, is_array: bool = False) -> str | None:
    """Extract JSON block from text using regex, handling potential preamble/postamble."""
    pattern = r"\[.*\]" if is_array else r"\{.*\}"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(0)
    
    # Fallback to simple strip if regex fails (e.g. malformed or very small)
    cleaned = text.strip()
    if cleaned.startswith("```"):
        try:
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        except ValueError:
            cleaned = cleaned[3:] # Just skip the ```
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_score_response(text: str) -> dict[str, Any]:
    """Parse the JSON response from Claude. Handles common formatting issues."""
    json_str = _extract_json(text, is_array=False)
    if not json_str:
        raise ValueError("No JSON object found in response")

    data = json.loads(json_str)
    
    # 1. Ensure fit_score exists even if LLM used a different key
    if "fit_score" not in data:
        data["fit_score"] = _get_score_from_dict(data)
        
    # 2. Normalize reasoning (sometimes returned as object with summaries)
    reasoning = data.get("reasoning", "")
    if isinstance(reasoning, dict):
        # Extract summary if available, otherwise join values
        if "summary" in reasoning:
            data["reasoning"] = str(reasoning["summary"])
        else:
            data["reasoning"] = "; ".join(f"{k}: {v}" for k, v in reasoning.items())
    elif not isinstance(reasoning, str):
        data["reasoning"] = str(reasoning)

    return data


def _build_batch_user_message(jobs: list[CandidateJob], max_desc_chars: int = 20000) -> str:
    """Build the user message containing multiple job postings."""
    from src.providers.utils import strip_html
    parts = []
    for i, job in enumerate(jobs, 1):
        raw_desc = job.description or "(No description available)"
        description = strip_html(raw_desc)[:max_desc_chars]
        parts.append(f"""<job id="{i}">
Title: {job.title}
Company: {job.company_name}
Location: {job.location}
Salary (extracted): {job.salary}
URL: {job.url}

Description:
{description}
</job>
{_format_company_context(job.company_metadata)}
{_format_location_context(job.location_metadata)}""")
    return "\n\n".join(parts) + "\n\nScore each job's fit for the candidate. Treat each job in complete isolation. For each reasoning string, mention only the current job and the candidate profile. Never mention job numbers, ordering, previous/next jobs, other jobs in the batch, or comparisons between jobs."


def _parse_batch_response(text: str, expected_count: int) -> list[dict] | None:
    """Parse JSON array of fit scores. Returns None if validation fails."""
    try:
        json_str = _extract_json(text, is_array=True)
        if not json_str:
            return None

        # Try json.loads()
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # One more attempt: check if it's a list but wrapped in something
            # (already covered by _extract_json but being defensive)
            return None

        # Validate structure (list of exactly expected_count dicts)
        if isinstance(data, list) and len(data) == expected_count:
            # Ensure each item has a fit_score (even if we have to extract it from a variant key)
            for item in data:
                if isinstance(item, dict) and "fit_score" not in item:
                    item["fit_score"] = _get_score_from_dict(item)
            
            if all(isinstance(d, dict) and "fit_score" in d for d in data):
                return data

    except Exception as e:
        logger.warning("Batch parse error: %s", e)
        # Log the raw text on failure to aid debugging
        logger.debug("Raw batch text that failed: %s", text)

    return None


async def score_job(
    client: AsyncAnthropic,
    job: CandidateJob,
    system_prompt: list[dict[str, Any]],
    profile_config: dict[str, Any] | None = None,
    model: str = "claude-haiku-4-5-20251001",
    max_desc_chars: int = 20000,
    rate_limiter: _ScoringRateLimiter | None = None,
) -> ScoredJob:
    """Score a single job using Claude API (Async).

    Returns a ScoredJob with fit assessment, or a zero-scored job on failure.
    """
    user_message = _build_user_message(job, max_desc_chars)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if rate_limiter is not None:
                await rate_limiter.wait_for_slot()

            response = await client.messages.create(
                model=model,
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text
            data = _parse_score_response(raw_text)

            metadata = _extract_metadata(data)
            raw_result = ScoredJob(
                db_id=job.db_id,
                ats_platform=job.ats_platform,
                company_slug=job.company_slug,
                company_name=job.company_name,
                job_id=job.job_id,
                title=job.title,
                location=job.location,
                company_metadata=job.company_metadata,
                location_metadata=job.location_metadata,
                url=job.url,
                description=job.description,
                posted_at=job.posted_at,
                first_seen_at=job.first_seen_at,
                fit_score=data.get("fit_score", 0),
                reasoning=data.get("reasoning", ""),
                breakdown=_get_breakdown_from_dict(data),
                key_matches=metadata["key_matches"],
                red_flags=metadata["red_flags"],
                apply_priority=metadata["apply_priority"],
                skip_reason=metadata["skip_reason"],
                missing_skills=metadata["missing_skills"],
                salary=metadata["salary"],
                salary_min=metadata["salary_min"],
                salary_max=metadata["salary_max"],
                salary_currency=metadata["salary_currency"],
                is_sparse=metadata["is_sparse"],
            )
            normalized_result = normalize_scored_job(raw_result)
            normalized_result = replace(
                normalized_result,
                fit_category=_derive_fit_category(job, normalized_result, profile_config),
            )
            _log_normalization(raw_result, normalized_result)
            return normalized_result

        except json.JSONDecodeError:
            logger.warning(
                "JSON parse error for %s @ %s (attempt %d/%d)",
                job.title, job.company_name, attempt, MAX_RETRIES,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1 * attempt)  # Exponential backoff
                continue
            # Return error score on final failure
            return _error_scored_job(job, "PARSE_ERROR")

        except anthropic.RateLimitError as error:
            wait = _rate_limit_wait_seconds(error, attempt, is_batch=False)
            if rate_limiter is not None:
                await rate_limiter.apply_cooldown(wait)
                logger.warning("Rate limited, delaying shared scorer for %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
            else:
                logger.warning("Rate limited, waiting %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
                await asyncio.sleep(wait)
            continue

        except anthropic.APIError as e:
            logger.warning(
                "API error for %s @ %s: %s (attempt %d/%d)",
                job.title, job.company_name, e, attempt, MAX_RETRIES,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
            return _error_scored_job(job, f"API_ERROR: {e}")

        except Exception as e:
            logger.error("Unexpected error scoring %s @ %s: %s", job.title, job.company_name, e)
            return _error_scored_job(job, f"ERROR: {e}")

    return _error_scored_job(job, "Temporary scoring failure: Anthropic rate limits persisted after retries.")


async def score_batch(
    client: AsyncAnthropic,
    jobs: list[CandidateJob],
    system_prompt: list[dict[str, Any]],
    profile_config: dict[str, Any] | None = None,
    model: str = "claude-haiku-4-5-20251001",
    max_desc_chars: int = 20000,
    rate_limiter: _ScoringRateLimiter | None = None,
) -> list[ScoredJob]:
    """Score multiple jobs at once (batching).
    
    If parsing fails, falls back to scoring each job individually.
    """
    if len(jobs) == 1:
        # Optimization: delegate to score_job for single-item batches
        return [await score_job(client, jobs[0], system_prompt, profile_config, model, max_desc_chars, rate_limiter)]

    user_message = _build_batch_user_message(jobs, max_desc_chars)
    max_tokens = min(800 * len(jobs), 4096)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if rate_limiter is not None:
                await rate_limiter.wait_for_slot()

            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text
            data = _parse_batch_response(raw_text, len(jobs))

            if data is not None:
                results = []
                for job, job_data in zip(jobs, data):
                    metadata = _extract_metadata(job_data)
                    raw_result = ScoredJob(
                        db_id=job.db_id,
                        ats_platform=job.ats_platform,
                        company_slug=job.company_slug,
                        company_name=job.company_name,
                        job_id=job.job_id,
                        title=job.title,
                        location=job.location,
                        company_metadata=job.company_metadata,
                        location_metadata=job.location_metadata,
                        url=job.url,
                        description=job.description,
                        posted_at=job.posted_at,
                        first_seen_at=job.first_seen_at,
                        fit_score=job_data.get("fit_score", 0),
                        reasoning=job_data.get("reasoning", ""),
                        breakdown=_get_breakdown_from_dict(job_data),
                        key_matches=metadata["key_matches"],
                        red_flags=metadata["red_flags"],
                        apply_priority=metadata["apply_priority"],
                        skip_reason=metadata["skip_reason"],
                        missing_skills=metadata["missing_skills"],
                        salary=metadata["salary"],
                        salary_min=metadata["salary_min"],
                        salary_max=metadata["salary_max"],
                        salary_currency=metadata["salary_currency"],
                        is_sparse=metadata["is_sparse"],
                    )
                    normalized_result = normalize_scored_job(raw_result)
                    normalized_result = replace(
                        normalized_result,
                        fit_category=_derive_fit_category(job, normalized_result, profile_config),
                    )
                    _log_normalization(raw_result, normalized_result)
                    results.append(normalized_result)
                return results

            # Fallback if None returned from parser
            logger.warning("Batch scoring fallback for %d jobs (parsing failed)", len(jobs))
            break # Exit retry loop and use fallback

        except anthropic.RateLimitError as error:
            wait = _rate_limit_wait_seconds(error, attempt, is_batch=True)
            if rate_limiter is not None:
                await rate_limiter.apply_cooldown(wait)
                logger.warning("Rate limited (batch), delaying shared scorer for %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
            else:
                logger.warning("Rate limited (batch), waiting %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
                await asyncio.sleep(wait)
            continue

        except (anthropic.APIError, json.JSONDecodeError) as e:
            logger.warning("API/JSON error in batch (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
            break

        except Exception as e:
            logger.error("Unexpected error in batch scoring: %s", e)
            break

    # Final fallback for any terminal failure: score each individually
    logger.info("Falling back to individual scoring for %d jobs...", len(jobs))
    tasks = [score_job(client, job, system_prompt, profile_config, model, max_desc_chars, rate_limiter) for job in jobs]
    return await asyncio.gather(*tasks)


@runtime_checkable
class ScorerProtocol(Protocol):
    """Interface for job scoring implementations."""
    def score_single(self, job: CandidateJob, profile_doc: str) -> ScoredJob: ...

class AnthropicScorer:
    """Default scorer using Claude Haiku with prompt caching."""
    
    def __init__(self, model: str = "claude-haiku-4-5-20251001", max_desc_chars: int = 20000, profile_dir: Path | None = None):
        self.model = model
        self.max_desc_chars = max_desc_chars
        self.profile_dir = profile_dir
        self._client = anthropic.Anthropic()
        self._system_prompt: list[dict] | None = None
        self._profile_doc: str | None = None
    
    def _ensure_system_prompt(self, profile_doc: str) -> list[dict]:
        """Build and cache system prompt."""
        if self._system_prompt is None or self._profile_doc != profile_doc:
            philosophy = load_scoring_philosophy(self.profile_dir)
            structure = load_prompt_structure()
            scoring_instructions = structure.format(scoring_philosophy=philosophy)
            self._system_prompt = _build_system_prompt(scoring_instructions, profile_doc)
            self._profile_doc = profile_doc
        return self._system_prompt
    
    async def score_single(self, job: CandidateJob, profile_doc: str) -> ScoredJob:
        """Score a single job using Claude API."""
        system_prompt = self._ensure_system_prompt(profile_doc)
        # Note: This would need an Async client in the class as well if used,
        # but the main pipeline uses score_jobs below.
        async with AsyncAnthropic() as client:
            return await score_job(
                client,
                job,
                system_prompt,
                None,
                self.model,
                self.max_desc_chars,
                _ScoringRateLimiter(),
            )


async def score_jobs(
    candidates: list[CandidateJob],
    profile_doc: str,
    scoring_config: dict[str, Any],
    store: Store,
    profile_dir: Path | None = None,
    profile_config: dict[str, Any] | None = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    concurrency: int = 25,
    batch_size: int = 5,
) -> list[ScoredJob]:
    """Score all candidate jobs in parallel using Claude API.

    Args:
        candidates: Jobs to score.
        profile_doc: The profile_doc.md content.
        scoring_config: The 'scoring' section from search_config.yaml.
        store: Store instance to persist scores immediately.
        profile_config: The 'keywords' or full config from search_config.yaml for prompt context.
        progress_callback: Optional callback receiving (current, total) counts.
        concurrency: Max number of simultaneous API calls.
        batch_size: Number of jobs to score in a single API call.

    Returns:
        List of ScoredJob results.
    """
    concurrency = scoring_config.get("concurrency", concurrency)
    batch_size = scoring_config.get("batch_size", batch_size)
    min_request_interval = scoring_config.get("min_request_interval_seconds", CALL_DELAY)

    model = scoring_config.get("model", "claude-haiku-4-5-20251001")
    max_desc_chars = scoring_config.get("max_description_chars", 20000)

    # Load scoring philosophy and assemble template
    philosophy = load_scoring_philosophy(profile_dir)
    structure = load_prompt_structure()
    scoring_instructions = structure.format(scoring_philosophy=philosophy)
    
    # Build system prompt (cached across all calls)
    system_prompt = _build_system_prompt(scoring_instructions, profile_doc, profile_config)

    total = len(candidates)
    num_batches = (total + batch_size - 1) // batch_size
    
    logger.info(
        "Scoring %d candidates in %d batches (concurrency=%d, batch_size=%d, min_interval=%.2fs) with %s...",
        total, num_batches, concurrency, batch_size, float(min_request_interval), model
    )

    batches = [candidates[i : i + batch_size] for i in range(0, total, batch_size)]
    semaphore = asyncio.Semaphore(concurrency)
    rate_limiter = _ScoringRateLimiter(min_request_interval)
    completed_count = 0

    async def worker(batch: list[CandidateJob], client: AsyncAnthropic) -> list[ScoredJob]:
        nonlocal completed_count
        async with semaphore:
            results = await score_batch(
                client,
                batch,
                system_prompt,
                profile_config,
                model,
                max_desc_chars,
                rate_limiter,
            )
            
            for result in results:
                # Persist score immediately
                store.update_score(
                    db_id=result.db_id,
                    fit_score=result.fit_score,
                    reasoning=result.reasoning,
                    breakdown=result.breakdown,
                    key_matches=result.key_matches,
                    red_flags=result.red_flags,
                    fit_category=result.fit_category,
                    apply_priority=result.apply_priority,
                    skip_reason=result.skip_reason,
                    missing_skills=result.missing_skills,
                    normalization_audit=result.normalization_audit,
                    salary=result.salary,
                    salary_min=result.salary_min,
                    salary_max=result.salary_max,
                    salary_currency=result.salary_currency,
                    is_sparse=result.is_sparse,
                )

            completed_count += len(batch)
            if progress_callback:
                progress_callback(completed_count, total)

            logger.info(
                "  → [%d/%d] Completed batch of %d", 
                completed_count, total, len(batch)
            )
            return results

    async with AsyncAnthropic() as client:
        tasks = [worker(batch, client) for batch in batches]
        all_results = await asyncio.gather(*tasks)

    # Flatten results
    scored = [job for batch_result in all_results for job in batch_result]
    return scored


def _error_scored_job(job: CandidateJob, reason: str) -> ScoredJob:
    """Create a zero-scored ScoredJob for error cases."""
    return ScoredJob(
        db_id=job.db_id,
        ats_platform=job.ats_platform,
        company_slug=job.company_slug,
        company_name=job.company_name,
        job_id=job.job_id,
        title=job.title,
        location=job.location,
        company_metadata=job.company_metadata,
        location_metadata=job.location_metadata,
        url=job.url,
        description=job.description,
        posted_at=job.posted_at,
        first_seen_at=job.first_seen_at,
        fit_score=0,
        reasoning=reason,
        fit_category="",
        apply_priority="skip",
    )
