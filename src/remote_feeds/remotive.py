from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import certifi
import httpx

from src.models import RawJob

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback

logger = logging.getLogger(__name__)


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
        from src.collector import strip_html

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
            company_name = item.get("company_name", "Unknown")
            # Slugify: lowercase, hyphens, no spaces/special chars
            company_slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
            
            job = RawJob(
                ats_platform="remotive",
                company_slug=company_slug,
                company_name=company_name,
                job_id=str(item.get("id", "")),
                title=(item.get("title") or "").strip(),
                location=item.get("candidate_required_location", ""),
                url=item.get("url", ""),
                description=strip_html(item.get("description", "")),
                posted_at=item.get("publication_date"),
                fetched_at=now,
            )
            raw_jobs.append(job)

        if progress_callback:
            progress_callback(1, 1)

        logger.info("Remotive: Fetched %d jobs", len(raw_jobs))
        return raw_jobs
