from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import certifi
import httpx

from src.models import RawJob

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback
from src.providers import slugify, strip_html

logger = logging.getLogger(__name__)

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"
REQUEST_TIMEOUT = 20
PAGE_DELAY_SECONDS = 1.0


def _created_at_to_iso(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str) and value.strip():
        return value
    return None


def _parse_arbeitnow_job(item: dict[str, object], fetched_at: str) -> RawJob:
    company_name = str(item.get("company_name") or "Unknown")
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "")
    location = str(item.get("location") or ("Remote" if item.get("remote") else ""))
    slug = str(item.get("slug") or "")

    return RawJob(
        ats_platform="arbeitnow",
        company_slug=slugify(company_name),
        company_name=company_name,
        job_id=slug or url,
        title=title,
        location=location,
        url=url,
        description=strip_html(str(item.get("description") or "")),
        posted_at=_created_at_to_iso(item.get("created_at")),
        fetched_at=fetched_at,
    )


async def _fetch_arbeitnow_page(client: httpx.AsyncClient, page: int) -> dict[str, Any] | None:
    try:
        resp = await client.get(BASE_URL, params={"page": page}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("Arbeitnow page %d fetch failed: %s", page, exc)
        return None


class ArbeitnowProvider:
    name = "arbeitnow"
    display_name = "Arbeitnow"
    description = "European tech jobs from Arbeitnow's public API. Attribution: arbeitnow.com."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        ssl_context = certifi.where()
        now = datetime.now(timezone.utc).isoformat()
        raw_jobs: list[RawJob] = []

        async with httpx.AsyncClient(verify=ssl_context) as client:
            page = 1
            total_pages: int | None = None

            while True:
                payload = await _fetch_arbeitnow_page(client, page)
                if payload is None:
                    break

                items = payload.get("data", [])
                if not isinstance(items, list):
                    logger.warning("Arbeitnow page %d returned unexpected data shape", page)
                    break

                for item in items:
                    if isinstance(item, dict):
                        raw_jobs.append(_parse_arbeitnow_job(item, now))

                meta = payload.get("meta", {})
                if isinstance(meta, dict):
                    current_page = meta.get("current_page")
                    if isinstance(current_page, int):
                        page = current_page

                links = payload.get("links", {})
                next_link = links.get("next") if isinstance(links, dict) else None

                if total_pages is None and isinstance(meta, dict):
                    current = meta.get("current_page")
                    per_page = meta.get("per_page")
                    to = meta.get("to")
                    if isinstance(current, int) and isinstance(per_page, int) and isinstance(to, int) and per_page > 0:
                        total_pages = max(current, (to + per_page - 1) // per_page)

                if progress_callback:
                    progress_callback(page, total_pages or page)

                if not next_link:
                    break

                page += 1
                await asyncio.sleep(PAGE_DELAY_SECONDS)

        logger.info("Arbeitnow: Fetched %d jobs", len(raw_jobs))
        return raw_jobs
