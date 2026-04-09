from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import certifi
import httpx

from src.models import RawJob

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback
from src.providers import slugify, strip_html

logger = logging.getLogger(__name__)

FEED_URL = "https://weworkremotely.com/remote-jobs.rss"
REQUEST_TIMEOUT = 20


def _parse_pub_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception:
        return value


def _split_title(value: str) -> tuple[str, str]:
    title = (value or "").strip()
    if ":" in title:
        company_name, job_title = title.split(":", 1)
        return company_name.strip() or "Unknown", job_title.strip()
    return "Unknown", title


def _parse_weworkremotely_item(item: ET.Element, fetched_at: str) -> RawJob:
    title_text = item.findtext("title", default="")
    company_name, title = _split_title(title_text)

    link = item.findtext("link", default="").strip()
    guid = item.findtext("guid", default="").strip()
    description_html = item.findtext("description", default="")

    return RawJob(
        ats_platform="weworkremotely",
        company_slug=slugify(company_name),
        company_name=company_name,
        job_id=guid or link,
        title=title,
        location="Remote",
        url=link,
        description=strip_html(description_html),
        posted_at=_parse_pub_date(item.findtext("pubDate")),
        fetched_at=fetched_at,
    )


def _parse_weworkremotely_feed(xml_text: str, fetched_at: str) -> list[RawJob]:
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")
    return [_parse_weworkremotely_item(item, fetched_at) for item in items]


class WeWorkRemotelyProvider:
    name = "weworkremotely"
    display_name = "We Work Remotely"
    description = "Remote jobs from We Work Remotely's public RSS feed. Attribution: weworkremotely.com."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        ssl_context = certifi.where()
        now = datetime.now(timezone.utc).isoformat()

        try:
            async with httpx.AsyncClient(verify=ssl_context) as client:
                resp = await client.get(FEED_URL, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                raw_jobs = _parse_weworkremotely_feed(resp.text, now)
        except Exception as exc:
            logger.warning("We Work Remotely fetch failed: %s", exc)
            return []

        if progress_callback:
            progress_callback(1, 1)

        logger.info("We Work Remotely: Fetched %d jobs", len(raw_jobs))
        return raw_jobs
