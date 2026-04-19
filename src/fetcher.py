import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional, Callable
from urllib.parse import urlparse

import certifi
import httpx

from src.job_resolver import resolve_job_ref
from src.providers.ats_resolvers import SINGLE_JOB_FETCHERS, fetch_supported_job
from src.providers.utils import strip_html
from src.models import RawJob
from src.providers.utils import slugify

logger = logging.getLogger(__name__)

def _humanize_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value or "").split("-") if part).strip()


def _guess_title_from_url(url: str, job_id: str, platform: str) -> str:
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    normalized_job_id = slugify(job_id)
    for part in reversed(path_parts):
        normalized = slugify(part)
        if not normalized or normalized == normalized_job_id:
            continue
        if normalized in {"jobs", "job", "careers", "positions", "apply"}:
            continue
        return _humanize_slug(normalized)
    return f"Imported {platform.title()} Job"


async def fetch_job_from_url(url: str) -> RawJob | None:
    """Best-effort ATS import helper for a single job URL."""
    ref = resolve_job_ref(url)
    if not ref.platform or not ref.company_slug or not ref.job_id:
        return None

    temp_job = SimpleNamespace(
        url=url,
        ats_platform=ref.platform,
        company_slug=ref.company_slug,
        company_name=_humanize_slug(ref.company_slug) or ref.company_slug,
    )
    sem = asyncio.Semaphore(1)

    async with httpx.AsyncClient(verify=certifi.where()) as client:
        resolved_job = await fetch_supported_job(client, ref)
        if resolved_job:
            return resolved_job

        description = await fetch_description(client, sem, temp_job)

    if not description:
        return None

    return RawJob(
        ats_platform=ref.platform,
        company_slug=ref.company_slug,
        company_name=_humanize_slug(ref.company_slug) or ref.company_slug,
        job_id=ref.job_id,
        title=_guess_title_from_url(url, ref.job_id, ref.platform),
        location="",
        url=url,
        description=description,
        posted_at=None,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )

def extract_json_ld(html: str) -> Optional[str]:
    """Try to find and parse schema.org JobPosting in JSON-LD."""
    def find_description(obj: Any) -> Optional[str]:
        """Recursively search for JobPosting or any description-like field."""
        if isinstance(obj, dict):
            # 1. Direct JobPosting hit
            type_val = str(obj.get("@type") or obj.get("type", "")).lower()
            if "jobposting" in type_val:
                desc = obj.get("description") or obj.get("jobDescription") or obj.get("descriptionHtml")
                if desc and isinstance(desc, str):
                    return desc
            
            # 2. Heuristic: if we see a field named "description", and it's a long string, use it
            # This helps with non-standard JSON-LD
            for k, v in obj.items():
                k_lower = k.lower()
                if ("description" in k_lower or "content" in k_lower) and isinstance(v, str) and len(v) > 100:
                    return v

            # 3. Search children recursively
            for v in obj.values():
                res = find_description(v)
                if res: return res
                
        elif isinstance(obj, list):
            for item in obj:
                res = find_description(item)
                if res: return res
        return None

    # Find all <script> tags with ld+json
    matches = re.finditer(r'<script[^>]*type=["\']application\/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    for m in matches:
        try:
            raw_text = m.group(1).strip()
            data = json.loads(raw_text)
            desc = find_description(data)
            if desc:
                return desc
        except (json.JSONDecodeError, Exception):
            continue
    return None

async def _fetch_description_via_supported_resolver(
    client: httpx.AsyncClient,
    url: str,
) -> str | None:
    ref = resolve_job_ref(url)
    if ref.platform not in SINGLE_JOB_FETCHERS:
        return None
    resolved_job = await fetch_supported_job(client, ref)
    if resolved_job and resolved_job.description:
        return resolved_job.description
    return None


def _apply_resolved_job_details(job_obj: Any, resolved_job: RawJob) -> None:
    """Mutate a candidate-like object with richer ATS-resolved job fields."""
    for attr in ("title", "location", "url", "description", "posted_at", "company_name"):
        value = getattr(resolved_job, attr, None)
        if value:
            setattr(job_obj, attr, value)

    for attr in ("company_metadata", "location_metadata"):
        value = getattr(resolved_job, attr, None)
        if value:
            setattr(job_obj, attr, value)

    for attr in ("salary", "salary_currency"):
        value = getattr(resolved_job, attr, None)
        if value is not None:
            setattr(job_obj, attr, value)

    for attr in ("salary_min", "salary_max"):
        value = getattr(resolved_job, attr, None)
        if value is not None:
            setattr(job_obj, attr, value)


async def _fetch_description_via_fallback_scrape(
    client: httpx.AsyncClient,
    *,
    url: str,
    company_name: str,
) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Cache-Control": "no-cache",
    }

    try:
        resp = await client.get(url, timeout=12, follow_redirects=True, headers=headers)
        if resp.status_code != 200:
            return None

        html = resp.text
        json_ld_desc = extract_json_ld(html)
        if json_ld_desc:
            return json_ld_desc

        for selector in [
            r'class=["\'][^"\']*(?:job-description|description|posting-content|job-detail-description)[^"\']*["\'][^>]*>(.*?)</div>',
            r'id=["\'][^"\']*(?:job-description|description|content)[^"\']*["\'][^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
            r'<main[^>]*>(.*?)</main>',
        ]:
            match = re.search(selector, html, re.DOTALL | re.IGNORECASE)
            if match:
                content_piece = match.group(1)
                if len(strip_html(content_piece)) > 200:
                    return content_piece

        content = strip_html(html)
        if len(content) > 300:
            return content
    except Exception as e:
        logger.debug("Scraper fallback failed for %s (%s): %s", company_name, url, e)
    return None


async def fetch_description(client: httpx.AsyncClient, sem: asyncio.Semaphore, job: Any) -> Optional[str]:
    """
    Given a job, fetch its full description using ATS resolvers first, then generic scraping.
    """
    async with sem:
        url = str(job.url or "")
        company_name = str(job.company_name or "")

        try:
            resolved = await _fetch_description_via_supported_resolver(client, url)
            if resolved:
                return resolved
        except Exception as e:
            logger.debug("API hydration failed for %s: %s", company_name, e)

        return await _fetch_description_via_fallback_scrape(
            client,
            url=url,
            company_name=company_name,
        )

async def populate_descriptions(
    jobs: list[Any], 
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> list[Any]:
    """Iterates through jobs and fetches missing descriptions asynchronously."""
    if not jobs:
        return []
        
    logger.info("Lazily fetching descriptions for %d candidate jobs...", len(jobs))
    sem = asyncio.Semaphore(10) # 10 concurrent requests to not spam
    ssl_context = certifi.where()
    
    completed = 0
    total = len(jobs)
    
    async with httpx.AsyncClient(verify=ssl_context) as client:
        # Maintain job-to-result mapping by wrapping the fetch call per job.
        async def fetch_and_assign(job_obj):
            url = str(job_obj.url or "")

            async with sem:
                resolved_job: RawJob | None = None
                try:
                    ref = resolve_job_ref(url)
                    if ref.platform in SINGLE_JOB_FETCHERS:
                        resolved_job = await fetch_supported_job(client, ref)
                except Exception as e:
                    logger.debug("API hydration failed for %s: %s", getattr(job_obj, "company_name", ""), e)

                if resolved_job:
                    _apply_resolved_job_details(job_obj, resolved_job)
                    return job_obj

                desc = await _fetch_description_via_fallback_scrape(
                    client,
                    url=url,
                    company_name=str(getattr(job_obj, "company_name", "") or ""),
                )
                if desc:
                    job_obj.description = desc
            return job_obj

        wrapped_tasks = [fetch_and_assign(j) for j in jobs]
        
        for task in asyncio.as_completed(wrapped_tasks):
            await task
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
            
    # Filter out ones that failed
    successful = [j for j in jobs if j.description]
    if len(successful) < len(jobs):
        logger.warning("Failed to fetch descriptions for %d jobs (they will be skipped)", len(jobs) - len(successful))
        
    return successful
