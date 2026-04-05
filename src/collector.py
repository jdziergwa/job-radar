"""ATS API fetcher — collects jobs from Greenhouse, Lever, Ashby, Workable.

Uses asyncio + aiohttp with a semaphore for polite concurrency.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import ssl

import aiohttp
import certifi

from src.models import RawJob

logger = logging.getLogger(__name__)

# Concurrency and timeout settings
MAX_CONCURRENT = 5
REQUEST_TIMEOUT = 10  # seconds

# SSL context using certifi for macOS compatibility
_ssl_ctx = ssl.create_default_context(cafile=certifi.where())


class HTMLStripper(HTMLParser):
    """Strip HTML tags from a string, keeping only text content."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._ignore_tags = {"script", "style", "noscript", "head"}
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._ignore_tags:
            self._ignore_depth += 1
            return
        
        if self._ignore_depth > 0:
            return

        if tag in ["p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6"]:
            self._parts.append("\n")
        elif tag == "li":
            self._parts.append("\n• ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignore_tags:
            self._ignore_depth = max(0, self._ignore_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignore_depth > 0:
            return
        # Clean up excessive whitespace in data block but keep newlines we added
        cleaned = " ".join(data.split())
        if cleaned:
            self._parts.append(cleaned)

    def get_text(self) -> str:
        # Avoid multiple consecutive newlines and leading/trailing whitespace
        text = "".join(self._parts).strip()
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text


def strip_html(html: str) -> str:
    """Remove HTML tags and return plain text."""
    if not html:
        return ""
    stripper = HTMLStripper()
    try:
        stripper.feed(html)
        return stripper.get_text().strip()
    except Exception:
        return html


# ── ATS Fetchers ────────────────────────────────────────────────────


async def fetch_greenhouse(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    company: dict[str, str],
) -> list[RawJob]:
    """Fetch jobs from Greenhouse boards API."""
    slug = company["slug"]
    name = company.get("name", slug)
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

    async with sem:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                if resp.status == 404:
                    logger.warning("Greenhouse 404 for %s — slug may be dead", slug)
                    return []
                if resp.status != 200:
                    logger.warning("Greenhouse %d for %s", resp.status, slug)
                    return []
                data = await resp.json()
        except asyncio.TimeoutError:
            logger.warning("Greenhouse timeout for %s", slug)
            return []
        except Exception as e:
            logger.warning("Greenhouse error for %s: %s", slug, e)
            return []

    now = datetime.now(timezone.utc).isoformat()
    jobs: list[RawJob] = []

    for item in data.get("jobs", []):
        location_obj = item.get("location") or {}
        location = location_obj.get("name", "") if isinstance(location_obj, dict) else str(location_obj)
        content = item.get("content", "")

        jobs.append(RawJob(
            ats_platform="greenhouse",
            company_slug=slug,
            company_name=name,
            job_id=str(item.get("id", "")),
            title=item.get("title", ""),
            location=location,
            url=item.get("absolute_url", ""),
            description=content, # Stop stripping HTML for Greenhouse — frontend handles it beautifully now
            posted_at=item.get("updated_at"),
            fetched_at=now,
        ))

    logger.debug("Greenhouse %s: %d jobs", slug, len(jobs))
    return jobs


async def fetch_lever(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    company: dict[str, str],
) -> list[RawJob]:
    """Fetch jobs from Lever postings API."""
    slug = company["slug"]
    name = company.get("name", slug)
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"

    async with sem:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                if resp.status == 404:
                    logger.warning("Lever 404 for %s — slug may be dead", slug)
                    return []
                if resp.status != 200:
                    logger.warning("Lever %d for %s", resp.status, slug)
                    return []
                data = await resp.json()
        except asyncio.TimeoutError:
            logger.warning("Lever timeout for %s", slug)
            return []
        except Exception as e:
            logger.warning("Lever error for %s: %s", slug, e)
            return []

    now = datetime.now(timezone.utc).isoformat()
    jobs: list[RawJob] = []

    if not isinstance(data, list):
        logger.warning("Lever unexpected response format for %s", slug)
        return []

    for item in data:
        categories = item.get("categories", {}) or {}
        location = categories.get("location", "") or ""
        # descriptionPlain is already available, but description (HTML) is better
        description = item.get("description") or item.get("descriptionPlain") or ""

        jobs.append(RawJob(
            ats_platform="lever",
            company_slug=slug,
            company_name=name,
            job_id=str(item.get("id", "")),
            title=item.get("text", ""),
            location=location,
            url=item.get("hostedUrl", ""),
            description=description,
            posted_at=None,
            fetched_at=now,
        ))

    logger.debug("Lever %s: %d jobs", slug, len(jobs))
    return jobs


async def fetch_ashby(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    company: dict[str, str],
) -> list[RawJob]:
    """Fetch jobs from Ashby posting API. Best-effort — may 404."""
    slug = company["slug"]
    name = company.get("name", slug)
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"

    async with sem:
        try:
            async with session.post(
                url,
                json={},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 404:
                    logger.warning("Ashby 404 for %s — endpoint may have changed", slug)
                    return []
                if resp.status != 200:
                    logger.warning("Ashby %d for %s", resp.status, slug)
                    return []
                data = await resp.json()
        except asyncio.TimeoutError:
            logger.warning("Ashby timeout for %s", slug)
            return []
        except Exception as e:
            logger.warning("Ashby error for %s: %s", slug, e)
            return []

    now = datetime.now(timezone.utc).isoformat()
    jobs: list[RawJob] = []

    for item in data.get("jobs", []):
        location = item.get("location", "") or ""
        if isinstance(location, dict):
            location = location.get("name", "")

        jobs.append(RawJob(
            ats_platform="ashby",
            company_slug=slug,
            company_name=name,
            job_id=str(item.get("id", "")),
            title=item.get("title", ""),
            location=location,
            url=f"https://jobs.ashbyhq.com/{slug}/{item.get('id', '')}",
            description="",  # Would need a second request per job — skip for now
            posted_at=item.get("publishedDate"),
            fetched_at=now,
        ))

    logger.debug("Ashby %s: %d jobs", slug, len(jobs))
    return jobs


async def fetch_workable(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    company: dict[str, str],
) -> list[RawJob]:
    """Fetch jobs from Workable v3 API. No descriptions available in list."""
    slug = company["slug"]
    name = company.get("name", slug)
    url = f"https://apply.workable.com/api/v3/accounts/{slug}/jobs"

    async with sem:
        try:
            async with session.post(
                url,
                json={"query": "", "location": [], "department": [], "worktype": []},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 404:
                    logger.warning("Workable 404 for %s — slug may be dead", slug)
                    return []
                if resp.status != 200:
                    logger.warning("Workable %d for %s", resp.status, slug)
                    return []
                data = await resp.json()
        except asyncio.TimeoutError:
            logger.warning("Workable timeout for %s", slug)
            return []
        except Exception as e:
            logger.warning("Workable error for %s: %s", slug, e)
            return []

    now = datetime.now(timezone.utc).isoformat()
    jobs: list[RawJob] = []

    for item in data.get("results", []):
        city = item.get("city", "") or ""
        country = item.get("country", "") or ""
        location = f"{city}, {country}".strip(", ") if city or country else ""

        job_url = item.get("url", "") or f"https://apply.workable.com/{slug}/j/{item.get('shortcode', item.get('id', ''))}/"

        jobs.append(RawJob(
            ats_platform="workable",
            company_slug=slug,
            company_name=name,
            job_id=str(item.get("id", item.get("shortcode", ""))),
            title=item.get("title", ""),
            location=location,
            url=job_url,
            description="",  # Workable list endpoint doesn't include descriptions
            posted_at=None,
            fetched_at=now,
        ))

    logger.debug("Workable %s: %d jobs", slug, len(jobs))
    return jobs


# ── Platform Dispatcher ─────────────────────────────────────────────

FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
}


async def collect_all(
    companies: dict[str, list[dict[str, str]]],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[RawJob]:
    """Fetch jobs from all configured ATS platforms and companies.

    Args:
        companies: Dict mapping platform name → list of {slug, name} dicts.
                   Loaded from the profile's companies.yaml.
        progress_callback: Optional callback receiving (current, total) company counts.

    Returns:
        Flat list of all fetched RawJob objects.
    """
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    all_jobs: list[RawJob] = []

    connector = aiohttp.TCPConnector(ssl=_ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks: list[asyncio.Task[list[RawJob]]] = []

        for platform, company_list in companies.items():
            fetcher = FETCHERS.get(platform)
            if fetcher is None:
                logger.warning("Unknown ATS platform: %s — skipping", platform)
                continue

            for company in company_list:
                task = asyncio.create_task(
                    fetcher(session, sem, company),
                    name=f"{platform}/{company.get('slug', '?')}",
                )
                tasks.append(task)

        total_companies = len(tasks)
        logger.info("Fetching from %d companies across %d platforms...",
                     total_companies, len(companies))

        completed_count = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed_count += 1
            
            if isinstance(result, Exception):
                logger.warning("An ATS fetch task failed: %s", result)
            elif isinstance(result, list):
                all_jobs.extend(result)
            
            if progress_callback:
                progress_callback(completed_count, total_companies)

    logger.info("Collected %d total jobs from ATS APIs", len(all_jobs))
    return all_jobs
