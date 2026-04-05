"""LLM scoring via Claude API — sends candidate jobs for fit assessment.

Uses anthropic SDK with prompt caching. System prompt (scoring instructions +
profile doc) is cached; user message (job posting) changes per call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable, Optional, Callable

import anthropic
from anthropic import AsyncAnthropic

from src.models import CandidateJob, ScoredJob
from src.store import Store

logger = logging.getLogger(__name__)

# Delay between API calls to be respectful
CALL_DELAY = 0.5  # seconds
MAX_RETRIES = 3


def load_scoring_prompt() -> str:
    """Load the generic scoring instructions from docs/SCORING_PROMPT.md.

    Extracts the system prompt text from the code block in the markdown.
    """
    path = Path("docs/SCORING_PROMPT.md")
    content = path.read_text(encoding="utf-8")

    # Extract the system prompt from the first code block
    # It's between the first ``` and the next ```
    lines = content.split("\n")
    in_block = False
    prompt_lines: list[str] = []
    block_count = 0

    for line in lines:
        if line.strip().startswith("```") and not in_block:
            block_count += 1
            if block_count == 1:  # First code block = system prompt
                in_block = True
                continue
        elif line.strip() == "```" and in_block:
            break
        elif in_block:
            prompt_lines.append(line)

    return "\n".join(prompt_lines).strip()


def _build_system_prompt(scoring_instructions: str, profile_doc: str, profile_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Build the system message with cache_control for prompt caching."""
    import yaml
    
    # Format the structured profile data (keywords/preferences) for the prompt
    preferences_block = ""
    if profile_config:
        formatted_config = yaml.dump(profile_config, sort_keys=False, default_flow_style=False)
        preferences_block = f"\n\nCANDIDATE PREFERENCES (from profile.yaml):\n\n{formatted_config}"

    return [{
        "type": "text",
        "text": f"{scoring_instructions}{preferences_block}\n\nCANDIDATE PROFILE (from profile_doc.md):\n\n{profile_doc}",
        "cache_control": {"type": "ephemeral"},
    }]


def _build_user_message(job: CandidateJob, max_desc_chars: int = 20000) -> str:
    """Build the user message containing the job posting."""
    from src.collector import strip_html
    
    raw_desc = job.description or "(No description available)"
    # Strip HTML to save tokens and avoid noise for the LLM
    description = strip_html(raw_desc)[:max_desc_chars]

    return f"""<job>
Title: {job.title}
Company: {job.company_name}
Location: {job.location}
URL: {job.url}

Description:
{description}
</job>

Score this job's fit for the candidate."""


def _parse_numeric_score(val: Any) -> int:
    """Safely convert any numeric-like value to an integer (0-100)."""
    if val is None:
        return 0
    try:
        if isinstance(val, str):
            # Handle "90%", "85/100", etc.
            clean_val = "".join(c for c in val if c.isdigit() or c == ".")
            return int(float(clean_val)) if clean_val else 0
        return int(float(val))
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

    return {
        "key_matches": get_field("key_matches", []),
        "red_flags": get_field("red_flags", []),
        "apply_priority": get_field("apply_priority", "skip"),
        "skip_reason": skip_reason,
        "missing_skills": missing_skills,
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
    from src.collector import strip_html
    parts = []
    for i, job in enumerate(jobs, 1):
        raw_desc = job.description or "(No description available)"
        description = strip_html(raw_desc)[:max_desc_chars]
        parts.append(f"""<job id="{i}">
Title: {job.title}
Company: {job.company_name}
Location: {job.location}
URL: {job.url}

Description:
{description}
</job>""")
    return "\n\n".join(parts) + "\n\nScore each job's fit for the candidate. Treat each job in complete isolation — do NOT reference other jobs in the batch within any job's reasoning."


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
    model: str = "claude-haiku-4-5-20251001",
    max_desc_chars: int = 20000,
) -> ScoredJob:
    """Score a single job using Claude API (Async).

    Returns a ScoredJob with fit assessment, or a zero-scored job on failure.
    """
    user_message = _build_user_message(job, max_desc_chars)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text
            data = _parse_score_response(raw_text)

            metadata = _extract_metadata(data)
            return ScoredJob(
                db_id=job.db_id,
                ats_platform=job.ats_platform,
                company_slug=job.company_slug,
                company_name=job.company_name,
                job_id=job.job_id,
                title=job.title,
                location=job.location,
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
            )

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

        except anthropic.RateLimitError:
            wait = 2 ** attempt
            logger.warning("Rate limited, waiting %ds (attempt %d/%d)", wait, attempt, MAX_RETRIES)
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

    return _error_scored_job(job, "MAX_RETRIES_EXCEEDED")


async def score_batch(
    client: AsyncAnthropic,
    jobs: list[CandidateJob],
    system_prompt: list[dict[str, Any]],
    model: str = "claude-haiku-4-5-20251001",
    max_desc_chars: int = 20000,
) -> list[ScoredJob]:
    """Score multiple jobs at once (batching).
    
    If parsing fails, falls back to scoring each job individually.
    """
    if len(jobs) == 1:
        # Optimization: delegate to score_job for single-item batches
        return [await score_job(client, jobs[0], system_prompt, model, max_desc_chars)]

    user_message = _build_batch_user_message(jobs, max_desc_chars)
    max_tokens = min(800 * len(jobs), 4096)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
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
                    results.append(ScoredJob(
                        db_id=job.db_id,
                        ats_platform=job.ats_platform,
                        company_slug=job.company_slug,
                        company_name=job.company_name,
                        job_id=job.job_id,
                        title=job.title,
                        location=job.location,
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
                    ))
                return results

            # Fallback if None returned from parser
            logger.warning("Batch scoring fallback for %d jobs (parsing failed)", len(jobs))
            break # Exit retry loop and use fallback

        except anthropic.RateLimitError:
            wait = 2 ** attempt * 2  # Longer backoff for batch calls
            logger.warning("Rate limited (batch), waiting %ds (attempt %d/%d)", wait, attempt, MAX_RETRIES)
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
    tasks = [score_job(client, job, system_prompt, model, max_desc_chars) for job in jobs]
    return await asyncio.gather(*tasks)


@runtime_checkable
class ScorerProtocol(Protocol):
    """Interface for job scoring implementations."""
    def score_single(self, job: CandidateJob, profile_doc: str) -> ScoredJob: ...

class AnthropicScorer:
    """Default scorer using Claude Haiku with prompt caching."""
    
    def __init__(self, model: str = "claude-haiku-4-5-20251001", max_desc_chars: int = 20000):
        self.model = model
        self.max_desc_chars = max_desc_chars
        self._client = anthropic.Anthropic()
        self._system_prompt: list[dict] | None = None
        self._profile_doc: str | None = None
    
    def _ensure_system_prompt(self, profile_doc: str) -> list[dict]:
        """Build and cache system prompt."""
        if self._system_prompt is None or self._profile_doc != profile_doc:
            scoring_instructions = load_scoring_prompt()
            self._system_prompt = _build_system_prompt(scoring_instructions, profile_doc)
            self._profile_doc = profile_doc
        return self._system_prompt
    
    async def score_single(self, job: CandidateJob, profile_doc: str) -> ScoredJob:
        """Score a single job using Claude API."""
        system_prompt = self._ensure_system_prompt(profile_doc)
        # Note: This would need an Async client in the class as well if used,
        # but the main pipeline uses score_jobs below.
        async with AsyncAnthropic() as client:
            return await score_job(client, job, system_prompt, self.model, self.max_desc_chars)


async def score_jobs(
    candidates: list[CandidateJob],
    profile_doc: str,
    scoring_config: dict[str, Any],
    store: Store,
    profile_config: dict[str, Any] | None = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    concurrency: int = 25,
    batch_size: int = 5,
) -> list[ScoredJob]:
    """Score all candidate jobs in parallel using Claude API.

    Args:
        candidates: Jobs to score.
        profile_doc: The profile_doc.md content.
        scoring_config: The 'scoring' section from profile.yaml.
        store: Store instance to persist scores immediately.
        profile_config: The 'keywords' or full config from profile.yaml for prompt context.
        progress_callback: Optional callback receiving (current, total) counts.
        concurrency: Max number of simultaneous API calls.
        batch_size: Number of jobs to score in a single API call.

    Returns:
        List of ScoredJob results.
    """
    concurrency = scoring_config.get("concurrency", concurrency)
    batch_size = scoring_config.get("batch_size", batch_size)
    
    model = scoring_config.get("model", "claude-haiku-4-5-20251001")
    max_desc_chars = scoring_config.get("max_description_chars", 20000)

    # Load scoring instructions
    scoring_instructions = load_scoring_prompt()

    # Build system prompt (cached across all calls)
    system_prompt = _build_system_prompt(scoring_instructions, profile_doc, profile_config)

    total = len(candidates)
    num_batches = (total + batch_size - 1) // batch_size
    
    logger.info(
        "Scoring %d candidates in %d batches (concurrency=%d, batch_size=%d) with %s...", 
        total, num_batches, concurrency, batch_size, model
    )

    batches = [candidates[i : i + batch_size] for i in range(0, total, batch_size)]
    semaphore = asyncio.Semaphore(concurrency)
    completed_count = 0

    async def worker(batch: list[CandidateJob], client: AsyncAnthropic) -> list[ScoredJob]:
        nonlocal completed_count
        async with semaphore:
            results = await score_batch(client, batch, system_prompt, model, max_desc_chars)
            
            for result in results:
                # Persist score immediately
                store.update_score(
                    db_id=result.db_id,
                    fit_score=result.fit_score,
                    reasoning=result.reasoning,
                    breakdown=result.breakdown,
                    key_matches=result.key_matches,
                    red_flags=result.red_flags,
                    apply_priority=result.apply_priority,
                    skip_reason=result.skip_reason,
                    missing_skills=result.missing_skills,
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
        url=job.url,
        description=job.description,
        posted_at=job.posted_at,
        first_seen_at=job.first_seen_at,
        fit_score=0,
        reasoning=reason,
    )
