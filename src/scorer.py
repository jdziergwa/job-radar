"""LLM scoring — sends candidate jobs for fit assessment through the LLM adapter.

The system prompt (scoring instructions + profile doc) is marked cacheable;
the user message (job posting) changes per call.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, runtime_checkable, Optional, Callable

from src.llm import (
    AITask,
    LLMAdapter,
    LLMAPIError,
    LLMNonRetryableError,
    LLMRateLimitError,
    get_adapter,
    load_model_overrides,
    resolve_model,
)
from src.log_file import excerpt
from src.models import CandidateJob, ScoredJob, ScoringProvenance
from src.score_normalization import (
    DIMENSION_WEIGHTS,
    VALID_PRIORITIES,
    VALID_SKIP_REASONS,
    compute_weighted_fit_score,
    normalize_scored_job,
)
from src.store import Store

logger = logging.getLogger(__name__)

# Delay between API calls to be respectful
CALL_DELAY = 0.5  # seconds
MAX_RETRIES = 3


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_SCORE_PROPERTIES = {
    "fit_score": {"type": "integer"},
    "breakdown": _object_schema({key: {"type": "integer"} for key in DIMENSION_WEIGHTS}),
    "reasoning": {"type": "string"},
    "key_matches": {"type": "array", "items": {"type": "string"}},
    "red_flags": {"type": "array", "items": {"type": "string"}},
    "apply_priority": {"type": "string", "enum": sorted(VALID_PRIORITIES)},
    "skip_reason": {"type": "string", "enum": sorted(VALID_SKIP_REASONS)},
    "missing_skills": {"type": "array", "items": {"type": "string"}},
    "salary_info": _object_schema({
        "salary": {"type": ["string", "null"]},
        "min": {"type": ["integer", "null"]},
        "max": {"type": ["integer", "null"]},
        "currency": {"type": ["string", "null"]},
    }),
    "is_sparse": {"type": "boolean"},
}
_SINGLE_SCORE_SCHEMA = _object_schema(_SCORE_PROPERTIES)
_BATCH_SCORE_SCHEMA = _object_schema({
    "jobs": {
        "type": "array",
        "items": _object_schema({"job_id": {"type": "integer"}, **_SCORE_PROPERTIES}),
    },
})


class _ScoringRateLimiter:
    """Coordinate request pacing, shared cooldowns and a shared stop across concurrent scorers."""

    def __init__(self, min_interval_seconds: float = CALL_DELAY):
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._next_request_at = 0.0
        self._cooldown_until = 0.0
        self._stopped_by: LLMNonRetryableError | None = None
        self._lock = asyncio.Lock()

    async def wait_for_slot(self) -> None:
        """Wait for this request's turn. Raises `LLMNonRetryableError` once scoring has been stopped."""
        self._raise_if_stopped()
        delay = 0.0
        async with self._lock:
            now = asyncio.get_running_loop().time()
            ready_at = max(now, self._next_request_at, self._cooldown_until)
            self._next_request_at = ready_at + self.min_interval_seconds if self.min_interval_seconds > 0 else ready_at
            delay = ready_at - now

        if delay > 0:
            await asyncio.sleep(delay)
            self._raise_if_stopped()

    def stop(self, error: LLMNonRetryableError) -> None:
        """Fail every later request with `error` instead of sending it."""
        if self._stopped_by is None:
            logger.error("Stopping scoring, retrying won't help: %s", error)
            self._stopped_by = error

    def _raise_if_stopped(self) -> None:
        if self._stopped_by is not None:
            raise LLMNonRetryableError(str(self._stopped_by))

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


def _rate_limit_wait_seconds(error: LLMRateLimitError, attempt: int, *, is_batch: bool) -> float:
    """Prefer server-provided retry headers, otherwise back off conservatively."""
    retry_after = error.retry_after
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


def _log_raw_response(context: str, text: str | None) -> None:
    """Log a short excerpt and the length of a bad LLM response; never the whole of it."""
    if text is None:
        return
    logger.warning("%s — raw response %s", context, excerpt(text))


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


def _build_system_prompt(scoring_instructions: str, profile_doc: str, profile_config: dict[str, Any] | None = None) -> str:
    """Build the system prompt text (sent as a cacheable system prompt)."""
    import yaml

    # Send only the scoring-relevant subset of config to avoid token-heavy
    # prefilter regex noise in the cached system prompt.
    preferences_block = ""
    if profile_config:
        prompt_config = _build_prompt_profile_config(profile_config)
        if prompt_config:
            formatted_config = yaml.dump(prompt_config, sort_keys=False, default_flow_style=False)
            preferences_block = f"\n\nCANDIDATE PREFERENCES (from search_config.yaml):\n\n{formatted_config}"

    return f"{scoring_instructions}{preferences_block}\n\nCANDIDATE PROFILE (from profile_doc.md):\n\n{profile_doc}"


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
    """Unicode-safe phrase normalizer for dedup and role matching."""
    cleaned = re.sub(r"[\W]+", " ", (text or "").lower(), flags=re.UNICODE)
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
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _normalize_description_text(text: str) -> str:
    """Clean whitespace while preserving paragraph breaks and bullets."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"(?<=\S)\s*([•●▪◦])\s+", r"\n\1 ", normalized)
    normalized = re.sub(r"\n[ \t]+", "\n", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _compact_description_for_scoring(
    text: str,
    max_chars: int = 12000,
    profile_config: dict[str, Any] | None = None,
) -> str:
    """Normalize, deduplicate paragraphs, and truncate from the end.

    Boilerplate (DEI, privacy, legal) is almost always at the bottom of job
    descriptions, so simple end-truncation acts as language-agnostic boilerplate
    removal.
    """
    cleaned = _normalize_description_text(text)
    if not cleaned:
        return ""

    # Deduplicate repeated paragraphs (common with some ATS platforms)
    seen: set[str] = set()
    kept: list[str] = []
    for paragraph in re.split(r"\n\s*\n", cleaned):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        # Unicode-safe normalization for dedup key
        key = re.sub(r"[\W]+", " ", paragraph.lower(), flags=re.UNICODE).strip()
        if key and key not in seen:
            seen.add(key)
            kept.append(paragraph)

    result = "\n\n".join(kept)

    # Truncate from the end — requirements and tech stack are near the top,
    # boilerplate and legal disclaimers are near the bottom.
    if len(result) > max_chars:
        result = result[:max_chars].rsplit("\n", 1)[0].rstrip()

    return result.strip() or cleaned[:max_chars].strip()


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


def _build_user_message(
    job: CandidateJob,
    max_desc_chars: int = 20000,
    profile_config: dict[str, Any] | None = None,
) -> str:
    """Build the user message containing the job posting."""
    from src.providers.utils import strip_html
    
    raw_desc = job.description or "(No description available)"
    description = _compact_description_for_scoring(
        strip_html(raw_desc),
        max_desc_chars,
        profile_config,
    )

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


def _parse_optional_int(val: Any) -> int | None:
    """Best-effort integer parsing for non-score metadata such as salary bounds."""
    if val is None:
        return None
    try:
        if isinstance(val, str):
            cleaned = "".join(c for c in val if c.isdigit() or c in {".", "-"})
            if not cleaned or cleaned in {"-", ".", "-."}:
                return None
            return int(round(float(cleaned)))
        return int(round(float(val)))
    except (ValueError, TypeError):
        return None


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
        "salary_min": _parse_optional_int(s_min),
        "salary_max": _parse_optional_int(s_max),
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
    """Parse the JSON response from the LLM. Handles common formatting issues."""
    json_str = _extract_json(text, is_array=False)
    if not json_str:
        raise ValueError("No JSON object found in response")

    data = json.loads(json_str)
    if not isinstance(data, dict):
        raise ValueError("Expected a score object")
    
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


def _build_batch_user_message(
    jobs: list[CandidateJob],
    max_desc_chars: int = 20000,
    profile_config: dict[str, Any] | None = None,
) -> str:
    """Build the user message containing multiple job postings."""
    from src.providers.utils import strip_html
    parts = []
    for i, job in enumerate(jobs, 1):
        raw_desc = job.description or "(No description available)"
        description = _compact_description_for_scoring(
            strip_html(raw_desc),
            max_desc_chars,
            profile_config,
        )
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


def _parse_batch_response(text: str, expected_count: int, *, structured: bool = False) -> list[dict] | None:
    """Parse JSON array of fit scores. Returns None if validation fails."""
    if structured:
        payload = json.loads(text)
        rows = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or len(rows) != expected_count:
            return None
        if any(not isinstance(row, dict) or type(row.get("job_id")) is not int for row in rows):
            return None
        by_id = {row["job_id"]: row for row in rows}
        if by_id.keys() != set(range(1, expected_count + 1)):
            return None
        return [by_id[job_id] for job_id in range(1, expected_count + 1)]

    try:
        json_str = _extract_json(text, is_array=True)
        if not json_str:
            logger.warning("Batch parse: no JSON array found in response")
            return None

        # Try json.loads()
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # One more attempt: check if it's a list but wrapped in something
            # (already covered by _extract_json but being defensive)
            logger.warning("Batch parse: invalid JSON (%s)", e)
            return None

        # Validate structure (list of exactly expected_count dicts)
        if isinstance(data, list) and len(data) == expected_count:
            # Ensure each item has a fit_score (even if we have to extract it from a variant key)
            for item in data:
                if isinstance(item, dict) and "fit_score" not in item:
                    item["fit_score"] = _get_score_from_dict(item)
            
            if all(isinstance(d, dict) and "fit_score" in d for d in data):
                return data
            logger.warning("Batch parse: array items are not all objects with a fit_score")
        else:
            logger.warning(
                "Batch parse: expected a list of %d items, got %s of length %s",
                expected_count, type(data).__name__, len(data) if isinstance(data, list) else "n/a",
            )

    except Exception as e:
        logger.warning("Batch parse error: %s", e)
        # Log the raw text on failure to aid debugging
        logger.debug("Raw batch text that failed: %s", excerpt(text))

    return None


async def score_job(
    adapter: LLMAdapter,
    job: CandidateJob,
    system_prompt: str,
    profile_config: dict[str, Any] | None = None,
    model: str | None = None,
    max_desc_chars: int = 20000,
    rate_limiter: _ScoringRateLimiter | None = None,
) -> ScoredJob:
    """Score a single job through the LLM adapter (Async).

    Returns a ScoredJob with fit assessment, or a zero-scored job on failure.
    """
    model = model or resolve_model(AITask.SCORING)
    user_message = _build_user_message(job, max_desc_chars, profile_config)
    label = f"{job.title} @ {job.company_name} (db_id={job.db_id})"

    for attempt in range(1, MAX_RETRIES + 1):
        raw_text: str | None = None
        try:
            if rate_limiter is not None:
                await rate_limiter.wait_for_slot()

            logger.debug(
                "Scoring single job %s via %s/%s (attempt %d/%d, user_chars=%d)",
                label, adapter.name, model, attempt, MAX_RETRIES, len(user_message),
            )
            response = await adapter.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                model=model,
                max_tokens=1536,
                cache_system=True,
                json_schema=_SINGLE_SCORE_SCHEMA,
                json_output=True,
            )

            raw_text = response.text
            data = _parse_score_response(raw_text)
            logger.debug(
                "Scored %s: fit_score=%s priority=%s", label, data.get("fit_score"), data.get("apply_priority")
            )

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
                provenance=ScoringProvenance(adapter.name, model),
            )
            normalized_result = normalize_scored_job(raw_result)
            normalized_result = replace(
                normalized_result,
                fit_category=_derive_fit_category(job, normalized_result, profile_config),
            )
            _log_normalization(raw_result, normalized_result)
            return normalized_result

        except ValueError as error:
            logger.warning(
                "Invalid score for %s @ %s (attempt %d/%d): %s",
                job.title, job.company_name, attempt, MAX_RETRIES, error,
            )
            _log_raw_response(f"Unparseable score for {label}", raw_text)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1 * attempt)  # Exponential backoff
                continue
            # Return error score on final failure
            logger.error("Giving up on %s after %d parse failures; recording a failed attempt", label, MAX_RETRIES)
            return _error_scored_job(job, "PARSE_ERROR")

        except LLMRateLimitError as error:
            wait = _rate_limit_wait_seconds(error, attempt, is_batch=False)
            if rate_limiter is not None:
                await rate_limiter.apply_cooldown(wait)
                logger.warning("Rate limited, delaying shared scorer for %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
            else:
                logger.warning("Rate limited, waiting %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
                await asyncio.sleep(wait)
            continue

        except LLMNonRetryableError as error:
            if rate_limiter is not None:
                rate_limiter.stop(error)
            logger.error("Not retrying %s; recording a failed attempt: %s", label, error)
            return _error_scored_job(job, f"API_ERROR: {error}")

        except LLMAPIError as e:
            logger.warning(
                "API error for %s @ %s: %s (attempt %d/%d)",
                job.title, job.company_name, e, attempt, MAX_RETRIES,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
            logger.error("Giving up on %s after %d API errors; recording a failed attempt: %s", label, MAX_RETRIES, e)
            return _error_scored_job(job, f"API_ERROR: {e}")

        except Exception as e:
            logger.exception("Unexpected error scoring %s; recording a failed attempt: %s", label, e)
            _log_raw_response(f"Response for {label} before the error", raw_text)
            return _error_scored_job(job, f"ERROR: {e}")

    logger.error("Giving up on %s: rate limits persisted after %d attempts; recording a failed attempt", label, MAX_RETRIES)
    return _error_scored_job(job, f"Temporary scoring failure: {adapter.display_name} rate limits persisted after retries.")


async def score_batch(
    adapter: LLMAdapter,
    jobs: list[CandidateJob],
    system_prompt: str,
    profile_config: dict[str, Any] | None = None,
    model: str | None = None,
    max_desc_chars: int = 20000,
    rate_limiter: _ScoringRateLimiter | None = None,
) -> list[ScoredJob]:
    """Score multiple jobs at once (batching).

    If parsing fails, falls back to scoring each job individually. An error retrying
    cannot fix fails every job in the batch without that fallback.
    """
    if len(jobs) == 1:
        # Optimization: delegate to score_job for single-item batches
        return [await score_job(adapter, jobs[0], system_prompt, profile_config, model, max_desc_chars, rate_limiter)]

    model = model or resolve_model(AITask.SCORING)
    user_message = _build_batch_user_message(jobs, max_desc_chars, profile_config)
    structured = adapter.supports_json_schema(model)
    if structured:
        user_message += '\nReturn an object with a "jobs" array. Set each result\'s integer "job_id" to its input job ID.'
    max_tokens = min(1280 * len(jobs), 8192) if structured else min(800 * len(jobs), 4096)

    batch_ids = [job.db_id for job in jobs]

    for attempt in range(1, MAX_RETRIES + 1):
        raw_text: str | None = None
        try:
            if rate_limiter is not None:
                await rate_limiter.wait_for_slot()

            logger.debug(
                "Scoring batch db_ids=%s via %s/%s (attempt %d/%d, max_tokens=%d, user_chars=%d)",
                batch_ids, adapter.name, model, attempt, MAX_RETRIES, max_tokens, len(user_message),
            )
            response = await adapter.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                model=model,
                max_tokens=max_tokens,
                cache_system=True,
                json_schema=_BATCH_SCORE_SCHEMA,
                json_output=True,
            )

            raw_text = response.text
            data = _parse_batch_response(raw_text, len(jobs), structured=structured)

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
                        provenance=ScoringProvenance(adapter.name, model),
                    )
                    normalized_result = normalize_scored_job(raw_result)
                    normalized_result = replace(
                        normalized_result,
                        fit_category=_derive_fit_category(job, normalized_result, profile_config),
                    )
                    _log_normalization(raw_result, normalized_result)
                    results.append(normalized_result)
                logger.debug(
                    "Scored batch db_ids=%s: fit_scores=%s", batch_ids, [r.fit_score for r in results]
                )
                return results

            # Fallback if None returned from parser
            logger.warning("Batch scoring fallback for %d jobs db_ids=%s (parsing failed)", len(jobs), batch_ids)
            _log_raw_response(f"Unparseable batch db_ids={batch_ids}", raw_text)
            break # Exit retry loop and use fallback

        except LLMRateLimitError as error:
            wait = _rate_limit_wait_seconds(error, attempt, is_batch=True)
            if rate_limiter is not None:
                await rate_limiter.apply_cooldown(wait)
                logger.warning("Rate limited (batch), delaying shared scorer for %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
            else:
                logger.warning("Rate limited (batch), waiting %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
                await asyncio.sleep(wait)
            continue

        except LLMNonRetryableError as error:
            if rate_limiter is not None:
                rate_limiter.stop(error)
            logger.error("Not retrying batch db_ids=%s or its jobs; recording failed attempts: %s", batch_ids, error)
            return [_error_scored_job(job, f"API_ERROR: {error}") for job in jobs]

        except (LLMAPIError, ValueError) as e:
            logger.warning("API/JSON error in batch db_ids=%s (attempt %d/%d): %s", batch_ids, attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
            break

        except Exception as e:
            logger.exception("Unexpected error in batch scoring db_ids=%s: %s", batch_ids, e)
            _log_raw_response(f"Batch response for db_ids={batch_ids} before the error", raw_text)
            break

    # Final fallback for any terminal failure: score each individually
    logger.info("Falling back to individual scoring for %d jobs...", len(jobs))
    tasks = [score_job(adapter, job, system_prompt, profile_config, model, max_desc_chars, rate_limiter) for job in jobs]
    return await asyncio.gather(*tasks)


@runtime_checkable
class ScorerProtocol(Protocol):
    """Interface for job scoring implementations."""
    def score_single(self, job: CandidateJob, profile_doc: str) -> ScoredJob: ...

class LLMScorer:
    """Default scorer using the active LLM Provider with a cacheable system prompt."""

    def __init__(self, model: str | None = None, max_desc_chars: int = 20000, profile_dir: Path | None = None):
        self.model = model or resolve_model(AITask.SCORING)
        self.max_desc_chars = max_desc_chars
        self.profile_dir = profile_dir
        self._system_prompt: str | None = None
        self._profile_doc: str | None = None
    
    def _ensure_system_prompt(self, profile_doc: str) -> str:
        """Build and cache system prompt."""
        if self._system_prompt is None or self._profile_doc != profile_doc:
            philosophy = load_scoring_philosophy(self.profile_dir)
            structure = load_prompt_structure()
            scoring_instructions = structure.format(scoring_philosophy=philosophy)
            self._system_prompt = _build_system_prompt(scoring_instructions, profile_doc)
            self._profile_doc = profile_doc
        return self._system_prompt
    
    async def score_single(self, job: CandidateJob, profile_doc: str) -> ScoredJob:
        """Score a single job through the LLM adapter."""
        system_prompt = self._ensure_system_prompt(profile_doc)
        adapter = get_adapter()
        try:
            return await score_job(
                adapter,
                job,
                system_prompt,
                None,
                self.model,
                self.max_desc_chars,
                _ScoringRateLimiter(),
            )
        finally:
            await adapter.aclose()


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
    """Score all candidate jobs in parallel through the LLM adapter.

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

    model = resolve_model(
        AITask.SCORING,
        profile_model=scoring_config.get("model"),
        settings_overrides=load_model_overrides(store),
    )
    max_desc_chars = scoring_config.get("max_description_chars", 20000)

    # Load scoring philosophy and assemble template
    philosophy = load_scoring_philosophy(profile_dir)
    structure = load_prompt_structure()
    scoring_instructions = structure.format(scoring_philosophy=philosophy)
    rubric_version = hashlib.sha256(scoring_instructions.encode()).hexdigest()
    
    # Build system prompt (cached across all calls)
    system_prompt = _build_system_prompt(scoring_instructions, profile_doc, profile_config)
    effective_profile_config = dict(profile_config or {})

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

    async def worker(batch: list[CandidateJob]) -> list[ScoredJob]:
        nonlocal completed_count
        async with semaphore:
            results = await score_batch(
                adapter,
                batch,
                system_prompt,
                effective_profile_config,
                model,
                max_desc_chars,
                rate_limiter,
            )
            
            for result in results:
                if result.scoring_error is not None:
                    store.record_scoring_failure(result.db_id, model, rubric_version, result.scoring_error)
                    continue
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
                    provenance=result.provenance,
                    salary=result.salary,
                    salary_min=result.salary_min,
                    salary_max=result.salary_max,
                    salary_currency=result.salary_currency,
                    is_sparse=result.is_sparse,
                    scoring_model=model,
                    rubric_version=rubric_version,
                )

            completed_count += len(batch)
            if progress_callback:
                progress_callback(completed_count, total)

            logger.info(
                "  → [%d/%d] Completed batch of %d", 
                completed_count, total, len(batch)
            )
            return results

    adapter = get_adapter()
    logger.info(
        "Scoring via LLM Provider %s (%s), model=%s, system_prompt_chars=%d",
        adapter.display_name, adapter.name, model, len(system_prompt),
    )
    try:
        all_results = await asyncio.gather(*(worker(batch) for batch in batches))
    except Exception:
        logger.exception("Scoring run aborted after %d/%d jobs", completed_count, total)
        raise
    finally:
        await adapter.aclose()

    # Flatten results
    scored = [job for batch_result in all_results for job in batch_result]
    failed = [job for job in scored if job.scoring_error is not None]
    if failed:
        logger.error(
            "Scoring finished: %d/%d jobs failed; their previous scores were kept (first reason: %s)",
            len(failed), len(scored), failed[0].scoring_error,
        )
    else:
        logger.info("Scoring finished: %d jobs scored", len(scored))
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
        scoring_error=reason,
        fit_category="",
        apply_priority="skip",
    )
