"""Helpers for deciding when descriptions should be hydrated and how to merge them."""

from __future__ import annotations

from src.models import CandidateJob
from src.providers.utils import strip_html


SPARSE_DESCRIPTION_THRESHOLD = 600


def description_text_length(description: str) -> int:
    """Measure description density using plain text length, not raw HTML length."""
    if not description:
        return 0
    return len(strip_html(description).strip())


def should_hydrate_description(
    job: CandidateJob,
    threshold: int = SPARSE_DESCRIPTION_THRESHOLD,
) -> bool:
    """Hydrate when a job has no description or only sparse content."""
    return description_text_length(job.description) < threshold


def merge_hydrated_description(original: str, hydrated: str) -> str:
    """Preserve useful original text when hydrating sparse descriptions."""
    hydrated_clean = (hydrated or "").strip()
    original_clean = (original or "").strip()

    if not hydrated_clean:
        return original_clean
    if not original_clean:
        return hydrated_clean

    if strip_html(original_clean) == strip_html(hydrated_clean):
        return hydrated_clean

    return f"{original_clean}\n\n---\n{hydrated_clean}"
