from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional

import certifi
import httpx

from src.models import RawJob

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback
from src.providers import parse_salary_string, slugify

logger = logging.getLogger(__name__)

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items"
REQUEST_TIMEOUT = 30
URL_PATTERN = re.compile(r'https?://[^\s<>"]+')


def _is_job_posting(text: str, author: str) -> bool:
    """Filter out non-job comments (candidates, meta-discussion, bot posts)."""
    if not text or len(text.strip()) < 50:
        return False
    if author == "whoishiring":
        return False

    lower = text.lower().lstrip()
    skip_prefixes = [
        "looking for work",
        "seeking",
        "freelancer available",
        "i'm looking",
        "i am looking",
        "available for",
    ]
    for prefix in skip_prefixes:
        if lower.startswith(prefix):
            return False

    return True


def _parse_job_comment(comment: dict, fetched_at: str) -> RawJob | None:
    """Parse a single HN comment into a RawJob, or None if it's not a job posting."""
    from src.providers.utils import strip_html

    comment_id = comment.get("id")
    author = comment.get("author", "")
    html_text = comment.get("text", "")

    if not html_text or not _is_job_posting(html_text, author):
        return None

    # 1. URL extraction (before stripping HTML for better accuracy)
    urls = URL_PATTERN.findall(html_text)
    job_url = urls[0] if urls else f"https://news.ycombinator.com/item?id={comment_id}"

    # 2. Strip HTML
    plain_text = strip_html(html_text)
    lines = [line.strip() for line in plain_text.split("\n") if line.strip()]
    if not lines:
        return None

    header_line = lines[0]
    parts = [p.strip() for p in header_line.split("|")]

    # 3. Parsing Title/Company/Location
    if len(parts) >= 2:
        company_name = parts[0]
        title = parts[1]
        location = parts[2] if len(parts) >= 3 else "Unknown"
    else:
        # Fallback: no pipes or only one part
        title = header_line[:200]
        company_name = "Unknown (HN)"
        location = "Unknown"

    company_slug = slugify(company_name)

    # 4. Salary extraction
    # Try header line first, then full description
    salary_str = None
    # Many HN posts put salary in the header line
    # We'll look for strings containing currency symbols, "salary" keyword, or "100k" style numbers
    for p in parts:
        lower_p = p.lower()
        if any(c in lower_p for c in ["$", "€", "£", "salary"]) or re.search(r"\d+k", lower_p):
            # Validate that there are some actual numbers or currency found
            s_min, s_max, s_cur = parse_salary_string(p)
            if s_min is not None or s_max is not None or s_cur is not None:
                salary_str = p
                break
    
    s_min, s_max, s_cur = parse_salary_string(salary_str)
    
    # If no salary found in header, we could try parsing the whole description
    # but that might be noisy. Let's stick to header or explicit mentions for now.

    return RawJob(
        ats_platform="hackernews",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(comment_id),
        title=title,
        location=location,
        url=job_url,
        description=plain_text,
        posted_at=comment.get("created_at"),
        fetched_at=fetched_at,
        salary=salary_str,
        salary_min=s_min,
        salary_max=s_max,
        salary_currency=s_cur,
    )


async def _find_hiring_threads(client: httpx.AsyncClient, months: int = 2) -> list[int]:
    """Find the most recent 'Who is Hiring?' thread IDs."""
    params = {
        "query": '"who is hiring"',
        "tags": "story,author_whoishiring",
        "hitsPerPage": months,
    }
    try:
        resp = await client.get(ALGOLIA_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [int(hit["objectID"]) for hit in data.get("hits", [])]
    except Exception as e:
        logger.warning("Failed to find HN hiring threads: %s", e)
        return []


async def _fetch_thread_jobs(client: httpx.AsyncClient, story_id: int, fetched_at: str) -> list[RawJob]:
    """Fetch all job postings from a single hiring thread."""
    url = f"{ALGOLIA_ITEM_URL}/{story_id}"
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch HN thread %d: %s", story_id, e)
        return []

    children = data.get("children", [])
    raw_jobs = []
    for child in children:
        # Only top-level comments are jobs
        if child.get("parent_id") == story_id:
            job = _parse_job_comment(child, fetched_at)
            if job:
                raw_jobs.append(job)
    
    return raw_jobs


class HackerNewsProvider:
    """HackerNews 'Who is Hiring?' provider."""

    name = "hackernews"
    display_name = "HN Who is Hiring"
    description = "Monthly hiring threads from Hacker News. Tech/startup focused."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        """Fetch jobs from the last 2 monthly HN hiring threads."""
        logger.info("Fetching jobs from Hacker News...")
        
        ssl_context = certifi.where()
        now = datetime.now(timezone.utc).isoformat()
        
        async with httpx.AsyncClient(verify=ssl_context) as client:
            thread_ids = await _find_hiring_threads(client)
            if not thread_ids:
                return []
            
            logger.info("Found %d HN hiring threads: %s", len(thread_ids), thread_ids)
            
            all_raw_jobs: list[RawJob] = []
            for i, story_id in enumerate(thread_ids):
                thread_jobs = await _fetch_thread_jobs(client, story_id, now)
                logger.info("HN thread %d: %d job postings", story_id, len(thread_jobs))
                all_raw_jobs.extend(thread_jobs)
                
                if progress_callback:
                    progress_callback(i + 1, len(thread_ids))
                    
        logger.info("HackerNews: Fetched %d jobs total", len(all_raw_jobs))
        return all_raw_jobs
