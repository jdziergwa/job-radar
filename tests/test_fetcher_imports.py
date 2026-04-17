import asyncio
from unittest import mock

from src import fetcher
from src.models import RawJob


def test_fetch_job_from_url_uses_ashby_board_api_for_real_job_fields():
    ashby_job_id = "11111111-2222-3333-4444-555555555555"

    class _FakeResponse:
        def __init__(self, *, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.get_calls: list[tuple[str, dict | None, int | None]] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None):
            self.get_calls.append((url, params, timeout))
            return _FakeResponse(
                status_code=200,
                payload={
                    "name": "Example Labs",
                    "jobs": [
                        {
                            "id": ashby_job_id,
                            "title": "Senior QA Platform Engineer",
                            "location": {"name": "London"},
                            "workplaceType": "Remote",
                            "descriptionHtml": "<p>Build reliable product quality systems.</p>",
                            "compensationTierSummary": "$170k - $210k USD",
                        }
                    ],
                },
            )

        async def post(self, *args, **kwargs):  # pragma: no cover - fail fast if old API shape is used unexpectedly
            raise AssertionError("Ashby import should use GET against the board API")

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url(
                f"https://jobs.ashbyhq.com/example-labs/{ashby_job_id}?utm_source=test-fixture"
            )

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="ashby",
        company_slug="example-labs",
        company_name="Example Labs",
        job_id=ashby_job_id,
        title="Senior QA Platform Engineer",
        location="Remote • London",
        url=f"https://jobs.ashbyhq.com/example-labs/{ashby_job_id}",
        description="<p>Build reliable product quality systems.</p>",
        posted_at=None,
        fetched_at=result.fetched_at,
        location_metadata={
            "raw_location": "Remote • London",
            "workplace_type": "Remote",
            "location_fragments": ["Remote • London"],
            "derived_geographic_signals": ["Remote role"],
        },
        salary="$170k - $210k USD",
    )
