from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import certifi
import httpx

from src.models import RawJob

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback
from src.providers import parse_salary_string, slugify

logger = logging.getLogger(__name__)

_API_URL = "https://jobicy.com/api/v2/remote-jobs"
_PAGE_SIZE = 50   # max allowed by the API
_MAX_JOBS = 500   # cap total jobs fetched


def _rfc2822_to_iso(value: str | None) -> str | None:
    """Convert an RFC 2822 date string (e.g. from Jobicy pubDate) to ISO 8601 UTC."""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception:
        return value  # return as-is if unparseable


def _parse_jobicy_job(item: dict[str, object], fetched_at: str) -> RawJob:
    from src.providers.utils import strip_html

    company_name = str(item.get("companyName", "Unknown"))
    company_slug = slugify(company_name)

    # Salary — Jobicy v2 does not consistently expose salary fields; handle gracefully
    s_min = item.get("annualSalaryMin")
    s_max = item.get("annualSalaryMax")
    s_cur = item.get("salaryCurrency")
    if s_min is None and s_max is None:
        salary_str = item.get("salary") or item.get("jobSalary")
        s_min, s_max, s_cur = parse_salary_string(
            salary_str if isinstance(salary_str, str) else None
        )
    else:
        s_min = int(s_min) if s_min is not None else None
        s_max = int(s_max) if s_max is not None else None
        s_cur = str(s_cur) if s_cur else None

    raw_desc = str(item.get("jobDescription") or item.get("jobExcerpt", ""))
    description = strip_html(raw_desc)

    return RawJob(
        ats_platform="jobicy",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(item.get("id", "")),
        title=str(item.get("jobTitle", "")).strip(),
        location=str(item.get("jobGeo", "")),
        url=str(item.get("url", "")),
        description=description,
        posted_at=_rfc2822_to_iso(
            item.get("pubDate") if isinstance(item.get("pubDate"), str) else None
        ),
        fetched_at=fetched_at,
        salary_min=s_min,
        salary_max=s_max,
        salary_currency=s_cur,
    )


class JobicyProvider:
    """Fetches jobs from Jobicy's public v2 API."""

    name = "jobicy"
    display_name = "Jobicy"
    description = "Remote jobs aggregator with EU coverage from Jobicy's public API."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        """Fetch current remote jobs from Jobicy (paginated, capped at 500)."""
        ssl_context = certifi.where()
        headers = {"User-Agent": "job-radar/1.0"}
        raw_jobs: list[RawJob] = []
        page = 1
        total_pages = (_MAX_JOBS + _PAGE_SIZE - 1) // _PAGE_SIZE  # 10

        logger.info("Fetching jobs from Jobicy (up to %d jobs)...", _MAX_JOBS)

        try:
            async with httpx.AsyncClient(verify=ssl_context, headers=headers) as client:
                while len(raw_jobs) < _MAX_JOBS:
                    params: dict[str, int] = {"count": _PAGE_SIZE}
                    if page > 1:
                        # API uses 'page' param for pagination; check if available
                        params["page"] = page

                    resp = await client.get(_API_URL, params=params, timeout=20)
                    resp.raise_for_status()
                    data = resp.json()

                    jobs = data.get("jobs", [])
                    if not jobs:
                        break  # exhausted

                    now = datetime.now(timezone.utc).isoformat()
                    for item in jobs:
                        if not isinstance(item, dict):
                            continue
                        raw_jobs.append(_parse_jobicy_job(item, now))

                    if progress_callback:
                        progress_callback(min(page, total_pages), total_pages)

                    # Jobicy may not support paging beyond page 1; stop if partial page
                    if len(jobs) < _PAGE_SIZE:
                        break

                    page += 1

        except Exception as e:
            logger.warning("Jobicy fetch failed: %s", e)
            return []

        if progress_callback:
            progress_callback(total_pages, total_pages)

        logger.info("Jobicy: fetched %d jobs", len(raw_jobs))
        return raw_jobs
