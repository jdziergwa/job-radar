from __future__ import annotations

import asyncio
import gzip
import io
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Optional, TYPE_CHECKING

import certifi
import httpx

from src.models import RawJob

logger = logging.getLogger(__name__)

MANIFEST_URLS = (
    "https://feashliaa.github.io/job-board-aggregator/data/chunks/jobs_manifest.json",
    "https://feashliaa.github.io/job-board-aggregator/data/jobs_manifest.json",
)

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback

MAX_CONCURRENT_CHUNKS = 5
CHUNK_TIMEOUT = 30  # seconds


async def fetch_chunk(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    chunk_base_url: str,
    chunk_filename: str,
) -> list[dict]:
    url = chunk_base_url + chunk_filename
    async with sem:
        try:
            logger.debug("Fetching chunk: %s", chunk_filename)
            response = await client.get(url, timeout=CHUNK_TIMEOUT)
            response.raise_for_status()

            # Decompress and load JSON
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
                data = json.load(f)

            return data
        except Exception as e:
            logger.warning("Failed to fetch chunk %s: %s", chunk_filename, e)
            return []

async def _fetch_manifest(client: httpx.AsyncClient) -> tuple[dict, str]:
    for manifest_url in MANIFEST_URLS:
        try:
            resp = await client.get(manifest_url, timeout=10)
            resp.raise_for_status()
            manifest = resp.json()
            chunk_base_url = manifest_url.rsplit("/", 1)[0] + "/"
            return manifest, chunk_base_url
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info("Aggregator manifest not found at %s, trying fallback", manifest_url)
                continue
            raise
        except Exception as e:
            logger.warning("Failed to fetch aggregator manifest from %s: %s", manifest_url, e)
            continue

    raise RuntimeError(f"Aggregator manifest unavailable at all known paths: {', '.join(MANIFEST_URLS)}")


async def get_aggregator_metadata() -> dict:
    """Fetch manifest and return metadata without chunks."""
    ssl_context = certifi.where()
    async with httpx.AsyncClient(verify=ssl_context) as client:
        try:
            manifest, _chunk_base_url = await _fetch_manifest(client)
            return {
                "last_updated": manifest.get("last_updated", "unknown"),
                "total_jobs": manifest.get("totalJobs", 0),
            }
        except Exception as e:
            logger.error("Failed to fetch aggregator metadata: %s", e)
            return {"last_updated": "unknown", "total_jobs": 0}


async def fetch_all_aggregator_jobs(progress_callback: Optional[Callable[[int, int], None]] = None) -> tuple[list[RawJob], str]:
    """Fetch all chunks from the remote job aggregator and convert to RawJob format."""
    logger.info("Initializing connection to job aggregator...")

    ssl_context = certifi.where()
    async with httpx.AsyncClient(verify=ssl_context) as client:
        try:
            manifest, chunk_base_url = await _fetch_manifest(client)
        except Exception as e:
            logger.error("Failed to fetch aggregator manifest: %s", e)
            return [], "unknown"

        chunks = manifest.get("chunks", [])
        total_expected = manifest.get("totalJobs", 0)
        last_updated = manifest.get("last_updated", "unknown")

        try:
            # Parse ISO 8601 strings like "2026-04-02T02:38:58.465457Z"
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            pretty_date = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError):
            pretty_date = last_updated

        logger.info("Aggregator data last updated on: %s", pretty_date)
        logger.info("Found %d chunks (expected ~%d jobs)", len(chunks), total_expected)

        sem = asyncio.Semaphore(MAX_CONCURRENT_CHUNKS)

        raw_jobs: list[RawJob] = []
        now = datetime.now(timezone.utc).isoformat()

        logger.info("Downloading chunks concurrently...")

        # We'll use as_completed to provide progress updates
        tasks = [fetch_chunk(client, sem, chunk_base_url, chunk) for chunk in chunks]
        completed_count = 0
        total_chunks = len(chunks)

        for task in asyncio.as_completed(tasks):
            chunk_data = await task
            completed_count += 1

            # Process results into RawJob objects
            for item in chunk_data:
                ats = str(item.get("ats", "")).lower()
                company_slug = str(item.get("company", ""))
                job_id_str = item.get("url", "")
                
                raw_jobs.append(RawJob(
                    ats_platform=ats,
                    company_slug=company_slug,
                    company_name=company_slug.title(),
                    job_id=job_id_str,
                    title=(item.get("title") or "").strip(),
                    location=(item.get("location") or "").strip(),
                    url=(item.get("url") or "").strip(),
                    description="",
                    posted_at=None,
                    fetched_at=now
                ))

            if progress_callback:
                progress_callback(completed_count, total_chunks)

    logger.info("Aggregator extraction complete. Yielded %d total jobs.", len(raw_jobs))
    return raw_jobs, last_updated


class AggregatorProvider:
    """Static chunk downloader (~910k jobs) from the global job-board-aggregator."""

    name = "aggregator"
    display_name = "Global Aggregator"
    description = "Broad Market: Scans 910k+ jobs from the open aggregator."
    shows_aggregator_badge = True
    last_updated: str = "unknown"

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        jobs, self.last_updated = await fetch_all_aggregator_jobs(progress_callback=progress_callback)
        return jobs
