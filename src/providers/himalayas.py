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

_API_URL = "https://himalayas.app/jobs/api"
_PAGE_SIZE = 20   # API enforces this limit regardless of the param value
_MAX_JOBS = 500   # cap to avoid excessive requests (~25 pages)


def _parse_himalayas_job(item: dict[str, object], fetched_at: str) -> RawJob:
    from src.providers.utils import strip_html

    company_name = str(item.get("companyName", "Unknown"))
    company_slug = str(item.get("companySlug") or slugify(company_name))

    # Location: list of strings -> join; or scalar string
    loc_raw = item.get("locationRestrictions") or item.get("locations", "")
    if isinstance(loc_raw, list):
        location = ", ".join(str(x) for x in loc_raw)
    else:
        location = str(loc_raw)

    # Use guid as job_id (stable URL-like string from Himalayas)
    job_id = str(item.get("guid") or item.get("id", ""))

    # URL — applicationLink preferred, fall back to guid itself (which is a URL)
    url = str(item.get("applicationLink") or item.get("url") or job_id)

    # Description
    raw_desc = str(item.get("description") or item.get("excerpt", ""))
    description = strip_html(raw_desc)

    # Salary
    s_min = item.get("minSalary")
    s_max = item.get("maxSalary")
    s_cur = item.get("currency")
    if s_min is None and s_max is None:
        salary_str = item.get("salary")
        s_min, s_max, s_cur = parse_salary_string(
            salary_str if isinstance(salary_str, str) else None
        )
    else:
        s_min = int(s_min) if s_min is not None else None
        s_max = int(s_max) if s_max is not None else None
        s_cur = str(s_cur) if s_cur else None

    posted_at = item.get("pubDate") or item.get("publishedAt")

    return RawJob(
        ats_platform="himalayas",
        company_slug=company_slug,
        company_name=company_name,
        job_id=job_id,
        title=str(item.get("title", "")).strip(),
        location=location,
        url=url,
        description=description,
        posted_at=str(posted_at) if posted_at is not None else None,
        fetched_at=fetched_at,
        salary_min=s_min,
        salary_max=s_max,
        salary_currency=s_cur,
    )


class HimalayasProvider:
    """Fetches jobs from Himalayas' public API."""

    name = "himalayas"
    display_name = "Himalayas"
    description = "Remote jobs from Himalayas' public API."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        """Fetch current jobs from Himalayas (paginated, capped at 500)."""
        ssl_context = certifi.where()
        headers = {"User-Agent": "job-radar/1.0"}
        raw_jobs: list[RawJob] = []
        offset = 0
        total_pages = (_MAX_JOBS + _PAGE_SIZE - 1) // _PAGE_SIZE  # 25

        logger.info("Fetching jobs from Himalayas (up to %d jobs)...", _MAX_JOBS)

        try:
            async with httpx.AsyncClient(verify=ssl_context, headers=headers) as client:
                while len(raw_jobs) < _MAX_JOBS:
                    resp = await client.get(
                        _API_URL,
                        params={"offset": offset},
                        timeout=20,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    jobs = data.get("jobs", [])
                    if not jobs:
                        break  # exhausted

                    now = datetime.now(timezone.utc).isoformat()
                    for item in jobs:
                        if not isinstance(item, dict):
                            continue
                        raw_jobs.append(_parse_himalayas_job(item, now))

                    offset += _PAGE_SIZE
                    pages_done = offset // _PAGE_SIZE

                    if progress_callback:
                        progress_callback(min(pages_done, total_pages), total_pages)

                    # Stop if response returned fewer items than one full page
                    if len(jobs) < _PAGE_SIZE:
                        break

        except Exception as e:
            logger.warning("Himalayas fetch failed: %s", e)
            return []

        if progress_callback:
            progress_callback(total_pages, total_pages)

        logger.info("Himalayas: fetched %d jobs", len(raw_jobs))
        return raw_jobs
