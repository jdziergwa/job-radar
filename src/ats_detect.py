from __future__ import annotations

import asyncio
import random
import re
import ssl
from typing import Callable

import certifi
import httpx

from src.company_import import extract_platform_slug_from_url


REQUEST_TIMEOUT = 10
MAX_HTML_CHARS = 100_000
DEFAULT_CONCURRENCY = 10
DEFAULT_REQUEST_DELAY_SECONDS = 0.5
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

HTML_ATS_PATTERNS = [
    (re.compile(r"""(?:src|href)=["']https?://boards\.greenhouse\.io/([a-z0-9_-]+)""", re.I), "greenhouse"),
    (re.compile(r"""(?:src|href)=["']https?://job-boards\.greenhouse\.io/([a-z0-9_-]+)""", re.I), "greenhouse"),
    (re.compile(r"""(?:src|href)=["']https?://jobs\.lever\.co/([a-z0-9_-]+)""", re.I), "lever"),
    (re.compile(r"""(?:src|href)=["']https?://jobs\.ashbyhq\.com/([a-z0-9_-]+)""", re.I), "ashby"),
    (re.compile(r"""(?:src|href)=["']https?://apply\.workable\.com/([a-z0-9_-]+)""", re.I), "workable"),
    (re.compile(r"""(?:src|href)=["']https?://([a-z0-9_-]+)\.bamboohr\.com""", re.I), "bamboohr"),
    (
        re.compile(r"""(?:src|href)=["']https?://(?:jobs|careers)\.smartrecruiters\.com/([a-z0-9_-]+)""", re.I),
        "smartrecruiters",
    ),
]


def _extract_career_url(record: dict) -> str | None:
    for key in ("jobBoardUrl", "careers_url", "careersUrl", "career_url", "job_board_url", "url"):
        value = record.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


def _match_html_ats(html: str) -> tuple[str | None, str | None]:
    for pattern, platform in HTML_ATS_PATTERNS:
        match = pattern.search(html)
        if match:
            return platform, match.group(1).strip().lower()
    return None, None


async def detect_ats(
    career_url: str,
    client: httpx.AsyncClient,
) -> tuple[str | None, str | None]:
    direct_platform, direct_slug = extract_platform_slug_from_url(career_url)
    if direct_platform and direct_slug:
        return direct_platform, direct_slug

    try:
        response = await client.get(career_url, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
    except (httpx.HTTPError, ValueError):
        return None, None

    final_platform, final_slug = extract_platform_slug_from_url(str(response.url))
    if final_platform and final_slug:
        return final_platform, final_slug

    if response.status_code >= 400:
        return None, None

    html_platform, html_slug = _match_html_ats(response.text[:MAX_HTML_CHARS])
    if html_platform and html_slug:
        return html_platform, html_slug

    return None, None


async def detect_ats_batch(
    companies: list[dict],
    concurrency: int = DEFAULT_CONCURRENCY,
    progress_callback: Callable[[int, int], None] | None = None,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
) -> list[dict]:
    if not companies:
        return []

    sem = asyncio.Semaphore(max(1, concurrency))
    ssl_context = certifi.where()
    total = len(companies)
    completed = 0
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with httpx.AsyncClient(verify=ssl_context, follow_redirects=True, headers=REQUEST_HEADERS) as client:
        async def enrich(index: int, record: dict) -> tuple[int, dict]:
            career_url = _extract_career_url(record)
            if not career_url:
                return index, dict(record)

            async with sem:
                if request_delay_seconds > 0:
                    await asyncio.sleep(random.uniform(0, request_delay_seconds))
                platform, slug = await detect_ats(career_url, client)

            enriched = dict(record)
            if platform and slug:
                enriched["platform"] = platform
                enriched["slug"] = slug
            return index, enriched

        tasks = [enrich(index, company) for index, company in enumerate(companies)]
        results: list[dict | None] = [None] * len(companies)
        for task in asyncio.as_completed(tasks):
            index, enriched = await task
            results[index] = enriched
            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    return [result for result in results if result is not None]
