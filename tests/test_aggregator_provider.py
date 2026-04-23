import gzip
import json

import httpx
import pytest

from src.providers import aggregator


pytestmark = [pytest.mark.anyio, pytest.mark.unit]
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _gzip_json(payload: list[dict]) -> bytes:
    return gzip.compress(json.dumps(payload).encode("utf-8"))


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        transport = kwargs.get("transport")
        if transport is None:
            raise AssertionError("transport is required for test client")
        self._client = _REAL_ASYNC_CLIENT(transport=transport)

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return await self._client.__aexit__(exc_type, exc, tb)

    async def get(self, *args, **kwargs):
        return await self._client.get(*args, **kwargs)


async def test_get_aggregator_metadata_prefers_current_chunks_manifest(monkeypatch):
    current_manifest_url = aggregator.MANIFEST_URLS[0]
    manifest = {
        "chunks": ["jobs_chunk_0.json.gz"],
        "totalJobs": 1534687,
        "last_updated": "2026-04-23T02:31:06.546475Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == current_manifest_url:
            return httpx.Response(200, json=manifest, request=request)
        raise AssertionError(f"Unexpected URL: {request.url}")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        aggregator.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(*args, transport=transport, **kwargs),
    )

    metadata = await aggregator.get_aggregator_metadata()

    assert metadata == {
        "last_updated": "2026-04-23T02:31:06.546475Z",
        "total_jobs": 1534687,
    }


async def test_fetch_all_aggregator_jobs_falls_back_to_legacy_manifest_path(monkeypatch):
    current_manifest_url, legacy_manifest_url = aggregator.MANIFEST_URLS
    chunk_url = "https://feashliaa.github.io/job-board-aggregator/data/jobs_chunk_0.json.gz"
    manifest = {
        "chunks": ["jobs_chunk_0.json.gz"],
        "totalJobs": 1,
        "last_updated": "2026-04-22T12:00:00Z",
    }
    payload = [{
        "ats": "Greenhouse",
        "company": "acme",
        "title": "Backend Engineer",
        "location": "Remote",
        "url": "https://example.com/jobs/1",
    }]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == current_manifest_url:
            return httpx.Response(404, request=request)
        if url == legacy_manifest_url:
            return httpx.Response(200, json=manifest, request=request)
        if url == chunk_url:
            return httpx.Response(200, content=_gzip_json(payload), request=request)
        raise AssertionError(f"Unexpected URL: {request.url}")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        aggregator.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(*args, transport=transport, **kwargs),
    )

    jobs, last_updated = await aggregator.fetch_all_aggregator_jobs()

    assert last_updated == "2026-04-22T12:00:00Z"
    assert len(jobs) == 1
    assert jobs[0].ats_platform == "greenhouse"
    assert jobs[0].company_slug == "acme"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].url == "https://example.com/jobs/1"
