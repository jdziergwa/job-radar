"""ATS API fetcher — collects jobs from Greenhouse, Lever, Ashby, Workable, BambooHR.

Uses asyncio + aiohttp with platform-specific concurrency limits for polite access.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback

import ssl

import aiohttp
import certifi

from src.models import RawJob

logger = logging.getLogger(__name__)

# Concurrency and timeout settings
REQUEST_TIMEOUT = 10  # seconds
PLATFORM_REQUEST_TIMEOUT = {
    "greenhouse": REQUEST_TIMEOUT,
    "lever": 30,
    "ashby": REQUEST_TIMEOUT,
    "workable": REQUEST_TIMEOUT,
    "bamboohr": REQUEST_TIMEOUT,
    "smartrecruiters": REQUEST_TIMEOUT,
}
PLATFORM_CONCURRENCY = {
    "greenhouse": 5,
    "lever": 3,
    "ashby": 3,
    "workable": 3,
    "bamboohr": 3,
    "smartrecruiters": 3,
}
PLATFORM_REQUEST_DELAY = {
    "greenhouse": 0.0,
    "lever": 0.0,
    "ashby": 0.0,
    "workable": 0.0,
    "bamboohr": 0.0,
    "smartrecruiters": 0.0,
}

# SSL context using certifi for macOS compatibility
_ssl_ctx = ssl.create_default_context(cafile=certifi.where())


_ASHBY_TEXT_KEYS = ("name", "label", "text", "value", "title")


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = " ".join(str(value).split()).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def _extract_ashby_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(_extract_ashby_text_values(item))
        return values
    if isinstance(value, dict):
        values: list[str] = []
        for key in _ASHBY_TEXT_KEYS:
            text = value.get(key)
            if isinstance(text, str):
                values.append(text)
        return values
    return []


def _extract_ashby_description(item: dict[str, Any]) -> str:
    for key in (
        "descriptionHtml",
        "descriptionPlain",
        "jobDescriptionHtml",
        "jobDescriptionPlain",
        "description",
    ):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _build_company_metadata(company: dict[str, Any]) -> dict[str, object]:
    signals = _dedupe_text(
        list(company.get("company_quality_signals", []) or [])
        + list(company.get("companyQualitySignals", []) or [])
    )
    if not signals:
        return {}
    return {
        "quality_signals": signals,
        "source": "companies_yaml",
    }


def _derive_geographic_signals(location_texts: list[str], description: str) -> list[str]:
    combined = " ".join(location_texts + ([description] if description else []))
    lowered = combined.lower()
    signals: list[str] = []

    def add(signal: str) -> None:
        if signal not in signals:
            signals.append(signal)

    if "remote" in lowered:
        add("Remote role")
    if re.search(r"\b(worldwide|global|anywhere)\b", lowered):
        add("Explicitly global or worldwide remote")
    if re.search(r"\b(us|u\.s\.|usa|united states)\b(?:[-\s]+only|\s+only|\s+based|\s+residents?)", lowered):
        add("Restricted to United States")
    if re.search(r"\bnorth america\b(?:[-\s]+only|\s+only)?", lowered):
        add("Restricted to North America")
    if re.search(r"\b(europe|eu)\b(?:[-\s]+only|\s+only)?", lowered):
        add("Restricted to Europe")
    if re.search(r"\bemea\b(?:[-\s]+only|\s+only)?", lowered):
        add("Restricted to EMEA")
    if re.search(r"\b(?:timezone|time zone|hours?\s+overlap|overlap\s+hours?|utc|gmt|cet|cest|eet|eest|est|edt|cst|cdt|mst|mdt|pst|pdt|eastern time|central time|mountain time|pacific time)\b", lowered):
        add("Timezone overlap requirement mentioned")

    return signals


def _build_ashby_location_metadata(item: dict[str, Any], location: str, description: str) -> dict[str, object]:
    fragments = _dedupe_text(
        [location]
        + _extract_ashby_text_values(item.get("secondaryLocations"))
        + _extract_ashby_text_values(item.get("locationRestrictions"))
        + _extract_ashby_text_values(item.get("remoteLocation"))
        + _extract_ashby_text_values(item.get("remoteLocations"))
    )

    metadata: dict[str, object] = {"raw_location": location}

    workplace_type = item.get("workplaceType")
    if isinstance(workplace_type, str) and workplace_type.strip():
        metadata["workplace_type"] = workplace_type.strip()

    employment_type = item.get("employmentType")
    if isinstance(employment_type, str) and employment_type.strip():
        metadata["employment_type"] = employment_type.strip()

    if fragments:
        metadata["location_fragments"] = fragments

    derived_signals = _derive_geographic_signals(fragments, description)
    if derived_signals:
        metadata["derived_geographic_signals"] = derived_signals

    return metadata





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
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=_platform_timeout("greenhouse"))) as resp:
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
    company_metadata = _build_company_metadata(company)

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
            company_metadata=company_metadata,
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
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=_platform_timeout("lever"))) as resp:
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
    company_metadata = _build_company_metadata(company)

    if not isinstance(data, list):
        logger.warning("Lever unexpected response format for %s", slug)
        return []

    for item in data:
        categories = item.get("categories", {}) or {}
        location = categories.get("location", "") or ""
        
        # Assemble full description from multiple potential fields
        # 'description' is usually the intro
        parts = []
        intro = item.get("description") or item.get("descriptionPlain") or ""
        if intro:
            parts.append(intro)
            
        # 'lists' contains structured sections like Requirements, Responsibilities
        lists = item.get("lists")
        if isinstance(lists, list):
            for section in lists:
                header = section.get("text")
                content = section.get("content")
                if content:
                    if header:
                        parts.append(f"<h3>{header}</h3>")
                    parts.append(content)
                    
        # 'additional' contains further info
        additional = item.get("additional") or item.get("additionalPlain")
        if additional:
            parts.append(f"<h3>Additional Information</h3>")
            parts.append(additional)
            
        description = "\n\n".join(parts) if parts else ""

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
            company_metadata=company_metadata,
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
            async with session.get(
                url,
                params={"includeCompensation": "true"},
                timeout=aiohttp.ClientTimeout(total=_platform_timeout("ashby")),
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
    company_metadata = _build_company_metadata(company)

    for item in data.get("jobs", []):
        location = item.get("location", "") or ""
        if isinstance(location, dict):
            location = location.get("name", "")
        description = _extract_ashby_description(item)
        location_metadata = _build_ashby_location_metadata(item, location, description)

        jobs.append(RawJob(
            ats_platform="ashby",
            company_slug=slug,
            company_name=name,
            job_id=str(item.get("id", "")),
            title=item.get("title", ""),
            location=location,
            url=f"https://jobs.ashbyhq.com/{slug}/{item.get('id', '')}",
            description=description,
            posted_at=item.get("publishedDate"),
            fetched_at=now,
            company_metadata=company_metadata,
            location_metadata=location_metadata,
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
                timeout=aiohttp.ClientTimeout(total=_platform_timeout("workable")),
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
    company_metadata = _build_company_metadata(company)

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
            company_metadata=company_metadata,
        ))

    logger.debug("Workable %s: %d jobs", slug, len(jobs))
    return jobs


async def fetch_bamboohr(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    company: dict[str, str],
) -> list[RawJob]:
    """Fetch jobs from BambooHR public listing (embed2.php)."""
    slug = company["slug"]
    name = company.get("name", slug)
    url = f"https://{slug}.bamboohr.com/jobs/embed2.php?company={slug}"

    async with sem:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=_platform_timeout("bamboohr"))) as resp:
                if resp.status == 404:
                    logger.warning("BambooHR 404 for %s — slug may be dead", slug)
                    return []
                if resp.status != 200:
                    logger.warning("BambooHR %d for %s", resp.status, slug)
                    return []
                html = await resp.text()
        except asyncio.TimeoutError:
            logger.warning("BambooHR timeout for %s", slug)
            return []
        except Exception as e:
            logger.warning("BambooHR error for %s: %s", slug, e)
            return []

    now = datetime.now(timezone.utc).isoformat()
    jobs: list[RawJob] = []
    company_metadata = _build_company_metadata(company)

    # BambooHR embed uses a simple list of <a> tags
    # Pattern: <a href="//subdomain.bamboohr.com/jobs/view.php?id=123" ... >Title</a>
    # Or: <a href="/jobs/view.php?id=123" ... >Title</a>
    # We look for /jobs/view.php?id= or /careers/ (new format)
    matches = re.finditer(
        r'<a\s+[^>]*href=["\']([^"\']*(?:/jobs/view\.php\?id=|/careers/)[^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        re.IGNORECASE | re.DOTALL
    )

    for match in matches:
        job_url = match.group(1).strip()
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()

        # Handle protocol-relative URLs
        if job_url.startswith("//"):
            job_url = f"https:{job_url}"
        elif job_url.startswith("/"):
            job_url = f"https://{slug}.bamboohr.com{job_url}"

        # Extract Job ID from URL
        job_id_match = re.search(r"[?&]id=(\d+)", job_url)
        if not job_id_match:
            # Try new format: /careers/123
            job_id_match = re.search(r"/careers/(\d+)", job_url)
        
        job_id = job_id_match.group(1) if job_id_match else job_url

        jobs.append(RawJob(
            ats_platform="bamboohr",
            company_slug=slug,
            company_name=name,
            job_id=job_id,
            title=title,
            location="", # BambooHR listings often don't show location in this view
            url=job_url,
            description="", # Stage 2 hydration will handle this
            posted_at=None,
            fetched_at=now,
            company_metadata=company_metadata,
        ))

    logger.debug("BambooHR %s: %d jobs", slug, len(jobs))
    return jobs


async def fetch_smartrecruiters(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    company: dict[str, str],
) -> list[RawJob]:
    """Fetch jobs from SmartRecruiters API."""
    slug = company["slug"]
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    
    async with semaphore:
        async with session.get(url) as response:
            if response.status == 404:
                logger.warning("SmartRecruiters company not found: %s", slug)
                return []
            response.raise_for_status()
            data = await response.json()

    jobs = []
    for item in data.get("content", []):
        job_id = item.get("id")
        title = item.get("name")
        
        # Build location string
        loc_data = item.get("location", {})
        city = loc_data.get("city")
        country = loc_data.get("country", "").upper()
        location_parts = [p for p in [city, country] if p]
        location = ", ".join(location_parts) or "Remote"
        
        # SmartRecruiters jobs are usually at jobs.smartrecruiters.com/{slug}/{id}
        job_url = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"
        
        jobs.append(RawJob(
            ats_platform="smartrecruiters",
            company_slug=slug,
            company_name=company.get("name", slug),
            title=title,
            location=location,
            url=job_url,
            posted_at=item.get("releasedDate"),
        ))
    
    return jobs


# ── Platform Dispatcher ─────────────────────────────────────────────

FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
    "bamboohr": fetch_bamboohr,
    "smartrecruiters": fetch_smartrecruiters,
}


def _platform_concurrency(platform: str, runtime_config: dict[str, object] | None = None) -> int:
    if runtime_config and runtime_config.get("slow_mode"):
        return 2
    return PLATFORM_CONCURRENCY.get(platform, 2)


def _platform_delay(platform: str, runtime_config: dict[str, object] | None = None) -> float:
    if runtime_config and runtime_config.get("slow_mode"):
        return 2.0
    return PLATFORM_REQUEST_DELAY.get(platform, 0.0)


def _platform_timeout(platform: str) -> float:
    return PLATFORM_REQUEST_TIMEOUT.get(platform, REQUEST_TIMEOUT)


def _build_platform_semaphores(
    companies: dict[str, list[dict[str, str]]],
    runtime_config: dict[str, object] | None = None,
) -> dict[str, asyncio.Semaphore]:
    return {
        platform: asyncio.Semaphore(_platform_concurrency(platform, runtime_config))
        for platform in companies
        if platform in FETCHERS
    }


async def _fetch_company_jobs(
    session: aiohttp.ClientSession,
    platform: str,
    company: dict[str, str],
    semaphores: dict[str, asyncio.Semaphore],
    runtime_config: dict[str, object] | None = None,
) -> list[RawJob]:
    fetcher = FETCHERS.get(platform)
    if fetcher is None:
        logger.warning("Unknown ATS platform: %s — skipping", platform)
        return []

    semaphore = semaphores[platform]

    try:
        result = await fetcher(session, semaphore, company)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("%s/%s fetch failed: %s", platform, company.get("slug", "?"), exc)
        return []

    delay = _platform_delay(platform, runtime_config)
    if delay > 0:
        await asyncio.sleep(delay)

    return result


async def collect_all(
    companies: dict[str, list[dict[str, str]]],
    progress_callback: Optional[Callable[[int, int], None]] = None,
    runtime_config: dict[str, object] | None = None,
) -> list[RawJob]:
    """Fetch jobs from all configured ATS platforms and companies.

    Args:
        companies: Dict mapping platform name → list of {slug, name} dicts.
                   Loaded from the profile's companies.yaml.
        progress_callback: Optional callback receiving (current, total) company counts.

    Returns:
        Flat list of all fetched RawJob objects.
    """
    all_jobs: list[RawJob] = []
    semaphores = _build_platform_semaphores(companies, runtime_config)

    connector = aiohttp.TCPConnector(ssl=_ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks: list[asyncio.Task[list[RawJob]]] = []

        for platform, company_list in companies.items():
            if platform not in FETCHERS:
                logger.warning("Unknown ATS platform: %s — skipping", platform)
                continue

            logger.info(
                "ATS platform %s: %d companies (concurrency=%d, delay=%.1fs)",
                platform,
                len(company_list),
                _platform_concurrency(platform, runtime_config),
                _platform_delay(platform, runtime_config),
            )

            for company in company_list:
                task = asyncio.create_task(
                    _fetch_company_jobs(session, platform, company, semaphores, runtime_config),
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

            if isinstance(result, list):
                all_jobs.extend(result)
            
            if progress_callback:
                progress_callback(completed_count, total_companies)

    logger.info("Collected %d total jobs from ATS APIs", len(all_jobs))
    return all_jobs




class LocalATSProvider:
    """Greenhouse, Lever, Ashby, Workable, BambooHR — scans curated company list via direct API."""

    name = "local"
    display_name = "Targeted Boards"
    description = "Direct Source: Scans your curated company list via direct API (Supports Greenhouse, Lever, Ashby, Workable, BambooHR, SmartRecruiters)."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        runtime_config = ctx.config.get("runtime", {}) if isinstance(ctx.config, dict) else {}
        return await collect_all(
            ctx.companies,
            progress_callback=progress_callback,
            runtime_config=runtime_config if isinstance(runtime_config, dict) else {},
        )
