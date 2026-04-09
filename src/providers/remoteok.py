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


def _parse_remoteok_job(item: dict[str, object], fetched_at: str) -> RawJob | None:
    from src.providers.utils import strip_html

    if "id" not in item:
        return None

    company_name = str(item.get("company", "Unknown"))
    company_slug = slugify(company_name)

    salary_str = item.get("salary")
    s_min, s_max, s_cur = parse_salary_string(salary_str if isinstance(salary_str, str) else None)

    return RawJob(
        ats_platform="remoteok",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(item.get("id", "")),
        title=str(item.get("position", "")).strip(),
        location=str(item.get("location", "Remote")),
        url=str(item.get("url", "")),
        description=strip_html(str(item.get("description", ""))),
        posted_at=str(item.get("date")) if item.get("date") is not None else None,
        fetched_at=fetched_at,
        salary=salary_str if isinstance(salary_str, str) else None,
        salary_min=s_min,
        salary_max=s_max,
        salary_currency=s_cur,
    )


class RemoteOKProvider:
    """Fetches jobs from RemoteOK's public API."""

    name = "remoteok"
    display_name = "RemoteOK"
    description = "Remote tech jobs from RemoteOK's public API."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        """Fetch all current jobs from RemoteOK. No pagination or auth required."""
        url = "https://remoteok.com/api"
        # RemoteOK requires a User-Agent or it may block the request
        headers = {"User-Agent": "job-radar/1.0"}
        ssl_context = certifi.where()
        
        logger.info("Fetching jobs from RemoteOK...")
        
        try:
            async with httpx.AsyncClient(verify=ssl_context, headers=headers) as client:
                resp = await client.get(url, timeout=15)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("RemoteOK fetch failed: %s", e)
            return []

        # RemoteOK returns an array where the first element is metadata/legal notice.
        if not isinstance(data, list) or len(data) <= 1:
            logger.warning("RemoteOK API returned unexpected format or no jobs")
            return []

        # Skip the first element (metadata)
        jobs = data[1:]
        
        now = datetime.now(timezone.utc).isoformat()
        raw_jobs: list[RawJob] = []

        for item in jobs:
            if not isinstance(item, dict):
                continue
            job = _parse_remoteok_job(item, now)
            if job is not None:
                raw_jobs.append(job)

        if progress_callback:
            progress_callback(1, 1)

        logger.info("RemoteOK: Fetched %d jobs", len(raw_jobs))
        return raw_jobs
