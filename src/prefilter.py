"""Keyword/regex pre-filter — fast pass before expensive LLM scoring.

Applies title patterns, exclusions, location patterns, and description signals.
Lenient on location per ARCHITECTURE.md "Pre-filter Location Relaxation".
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Optional

from src.models import CandidateJob, RawJob

logger = logging.getLogger(__name__)


def prefilter(
    jobs: list[CandidateJob],
    keywords_config: dict[str, Any],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> tuple[list[CandidateJob], list[tuple[CandidateJob, str]]]:
    """Apply keyword/regex filters and return (survivors, rejected_with_reasons)."""
    title_config = keywords_config.get("title_patterns", {})
    if isinstance(title_config, list):
        high_conf_patterns = _compile_patterns(title_config)
        broad_patterns = []
    else:
        high_conf_patterns = _compile_patterns(title_config.get("high_confidence", []))
        broad_patterns = _compile_patterns(title_config.get("broad", []))

    exclusion_patterns = _compile_patterns(keywords_config.get("exclusions", []))
    location_patterns = _compile_patterns(keywords_config.get("location_patterns", []))
    location_exclusions = _compile_patterns(keywords_config.get("location_exclusions", []))
    
    # New: Configurable remote fallback tokens
    remote_patterns = _compile_patterns(keywords_config.get("remote_patterns", []))
    fallback_tier = keywords_config.get("fallback_tier", "broad_match")

    desc_signals_config = keywords_config.get("description_signals", {})
    desc_patterns = _compile_patterns(desc_signals_config.get("patterns", []))
    desc_min_matches = desc_signals_config.get("min_matches", 1)

    total = len(jobs)
    survivors: list[CandidateJob] = []
    rejected: list[tuple[CandidateJob, str]] = []

    for i, job in enumerate(jobs):
        # 1. Title match check (must match at least one tier)
        is_high_conf = _any_match(high_conf_patterns, job.title)
        is_broad = _any_match(broad_patterns, job.title)

        if not is_high_conf and not is_broad:
            rejected.append((job, "Failed Title Filter"))
            continue
        
        # 2. Exclusions — any match → skip
        found_excl = False
        for p in exclusion_patterns:
            if p.search(job.title):
                rejected.append((job, f"Excluded: {p.pattern}"))
                found_excl = True
                break
        
        if found_excl:
            continue

        # 3. Location — Config-driven approach
        loc_passed, loc_reason, is_fallback = _check_location_configly(
            job, 
            location_patterns, 
            location_exclusions,
            remote_patterns
        )
        if not loc_passed:
            rejected.append((job, loc_reason))
            continue

        # 4. Tiered Pass Strategy
        if is_fallback:
            # If it only passed via remote fallback, use the configured fallback tier
            job.match_tier = fallback_tier
            survivors.append(job)
        elif is_high_conf:
            # Tier 1: High Confidence Title Pass
            job.match_tier = "high_confidence"
            survivors.append(job)
        else:
            # Tier 2: Broad Title Match (Requires description signals)
            if job.description and desc_patterns:
                matches = [p.pattern for p in desc_patterns if p.search(job.description)]
                if len(matches) < desc_min_matches:
                    rejected.append((job, f"Insufficient Signals (Found: {', '.join(matches) or 'None'})"))
                else:
                    job.match_tier = "broad_match"
                    survivors.append(job)
            else:
                if not desc_patterns:
                    job.match_tier = "broad_match"
                    survivors.append(job)
                else:
                    rejected.append((job, "Insufficient Signals (No Description)"))

        # Progress reporting
        if progress_callback and (i + 1) % 10 == 0:
            progress_callback(i + 1, total)

    if progress_callback and total > 0:
        progress_callback(total, total)

    logger.info(
        "Pre-filter result: %d/%d survived",
        len(survivors),
        total,
    )

    return survivors, rejected


def _check_location_configly(
    job: CandidateJob, 
    location_patterns: list[re.Pattern[str]], 
    location_exclusions: list[re.Pattern[str]],
    remote_patterns: list[re.Pattern[str]]
) -> tuple[bool, str, bool]:
    """Check location and return (passed, reason_if_failed, is_fallback)."""
    location = job.location.strip()

    # 1. Strict Exclusion check first!
    if location_exclusions and location:
        for p in location_exclusions:
            if p.search(location):
                return False, f"Location Excluded: {p.pattern}", False

    # Empty location → pass (LLM will assess)
    if not location:
        return True, "", True

    # No location patterns AND no remote patterns? pass everything (unfiltered mode)
    if not location_patterns and not remote_patterns:
        return True, "", False

    # 2. Main Location Match
    if location_patterns and _any_match(location_patterns, location):
        return True, "", False

    # 3. Remote Fallback (if configured)
    if remote_patterns:
        # Check location itself for remote words
        if _any_match(remote_patterns, location):
            return True, "", True
        
        # Check description for remote words
        if job.description and _any_match(remote_patterns, job.description):
            return True, "", True

    # Hard reject if location is specified but doesn't match and no remote fallback triggered
    if location_patterns:
        return False, f"Location Mismatch: {location}", False
    
    # If only remote patterns are defined, and it didn't match, we reject if location is present
    return False, f"Not Remote: {location}", False


def _compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    """Compile a list of regex pattern strings, skipping invalid ones."""
    compiled: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error as e:
            logger.warning("Invalid regex pattern '%s': %s", p, e)
    return compiled


def _any_match(patterns: list[re.Pattern[str]], text: str) -> bool:
    """Return True if any pattern matches the text."""
    return any(p.search(text) for p in patterns)
