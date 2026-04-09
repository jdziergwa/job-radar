from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import certifi
import httpx

from src.models import RawJob

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback
from src.providers import parse_salary_string, slugify

logger = logging.getLogger(__name__)


def _parse_remotive_job(item: dict[str, object], fetched_at: str) -> RawJob:
    from src.providers.utils import strip_html

    company_name = str(item.get("company_name", "Unknown"))
    company_slug = slugify(company_name)

    salary_str = item.get("salary")
    s_min, s_max, s_cur = parse_salary_string(salary_str if isinstance(salary_str, str) else None)

    return RawJob(
        ats_platform="remotive",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(item.get("id", "")),
        title=str(item.get("title", "")).strip(),
        location=str(item.get("candidate_required_location", "")),
        url=str(item.get("url", "")),
        description=strip_html(str(item.get("description", ""))),
        posted_at=str(item.get("publication_date")) if item.get("publication_date") is not None else None,
        fetched_at=fetched_at,
        salary=salary_str if isinstance(salary_str, str) else None,
        salary_min=s_min,
        salary_max=s_max,
        salary_currency=s_cur,
    )


class RemotiveProvider:
    """Fetches jobs from Remotive's public API."""

    name = "remotive"
    display_name = "Remotive"
    description = "Remote tech jobs (Free Tier: 20 most recent jobs)."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        """Fetch all current jobs from Remotive. No pagination or auth required."""
        url = "https://remotive.com/api/remote-jobs"
        ssl_context = certifi.where()
        
        logger.info("Fetching jobs from Remotive...")
        
        try:
            async with httpx.AsyncClient(verify=ssl_context) as client:
                resp = await client.get(url, timeout=15)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("Remotive fetch failed: %s", e)
            return []

        jobs = data.get("jobs", [])
        if not jobs:
            logger.warning("Remotive API returned no jobs")
            return []

        now = datetime.now(timezone.utc).isoformat()
        raw_jobs: list[RawJob] = []

        for item in jobs:
            if not isinstance(item, dict):
                continue
            raw_jobs.append(_parse_remotive_job(item, now))

        if progress_callback:
            progress_callback(1, 1)

        logger.info("Remotive: Fetched %d jobs", len(raw_jobs))
        return raw_jobs
