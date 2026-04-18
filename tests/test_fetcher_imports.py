import asyncio
from unittest import mock

from src import fetcher
from src.models import RawJob


def test_fetch_job_from_url_uses_ashby_resolver_for_normalized_raw_job():
    ashby_job_id = "11111111-2222-3333-4444-555555555555"

    class _FakeResponse:
        def __init__(self, *, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None):
            assert url == "https://api.ashbyhq.com/posting-api/job-board/example-labs"
            assert params == {"includeCompensation": "true"}
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
        location="London",
        url=f"https://jobs.ashbyhq.com/example-labs/{ashby_job_id}",
        description="<p>Build reliable product quality systems.</p>",
        posted_at=None,
        fetched_at=result.fetched_at,
        location_metadata={
            "raw_location": "London",
            "workplace_type": "Remote",
            "location_fragments": ["London"],
        },
        salary="$170k - $210k USD",
    )


def test_fetch_job_from_url_uses_greenhouse_resolver_for_normalized_raw_job():
    class _FakeResponse:
        def __init__(self, *, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None):
            assert url == "https://boards-api.greenhouse.io/v1/boards/example-team/jobs/12345"
            return _FakeResponse(
                status_code=200,
                payload={
                    "id": 12345,
                    "title": "Backend Test Engineer",
                    "absolute_url": "https://boards.greenhouse.io/example-team/jobs/12345",
                    "updated_at": "2026-04-18T10:00:00Z",
                    "location": {"name": "Remote"},
                    "content": "<p>Own quality across backend services.</p>",
                },
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url("https://boards.greenhouse.io/example-team/jobs/12345")

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="greenhouse",
        company_slug="example-team",
        company_name="Example Team",
        job_id="12345",
        title="Backend Test Engineer",
        location="Remote",
        url="https://boards.greenhouse.io/example-team/jobs/12345",
        description="<p>Own quality across backend services.</p>",
        posted_at="2026-04-18T10:00:00Z",
        fetched_at=result.fetched_at,
    )


def test_fetch_job_from_url_uses_lever_resolver_for_normalized_raw_job():
    class _FakeResponse:
        def __init__(self, *, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None):
            assert url == "https://api.lever.co/v0/postings/example-team/abc-123"
            return _FakeResponse(
                status_code=200,
                payload={
                    "id": "abc-123",
                    "text": "Quality Automation Engineer",
                    "hostedUrl": "https://jobs.lever.co/example-team/abc-123",
                    "categories": {"location": "Remote EU"},
                    "description": "<p>Lead quality automation.</p>",
                    "lists": [
                        {"text": "Responsibilities", "content": "<ul><li>Write tests</li></ul>"},
                        {"text": "Requirements", "content": ["Python", "Playwright"]},
                    ],
                    "additional": "<p>Great async culture.</p>",
                },
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url("https://jobs.lever.co/example-team/abc-123")

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="lever",
        company_slug="example-team",
        company_name="Example Team",
        job_id="abc-123",
        title="Quality Automation Engineer",
        location="Remote EU",
        url="https://jobs.lever.co/example-team/abc-123",
        description=(
            "<p>Lead quality automation.</p>\n\n"
            "<h3>Responsibilities</h3>\n\n"
            "<ul><li>Write tests</li></ul>\n\n"
            "<h3>Requirements</h3>\n\n"
            "<ul><li>Python</li><li>Playwright</li></ul>\n\n"
            "<h3>Additional Information</h3>\n\n"
            "<p>Great async culture.</p>"
        ),
        posted_at=None,
        fetched_at=result.fetched_at,
    )


def test_fetch_job_from_url_uses_workable_resolver_for_normalized_raw_job():
    class _FakeResponse:
        def __init__(self, *, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None):
            assert url == "https://apply.workable.com/api/v3/accounts/example-team/jobs/job-777"
            return _FakeResponse(
                status_code=200,
                payload={
                    "id": "job-777",
                    "shortcode": "short-777",
                    "title": "Staff Quality Engineer",
                    "city": "Berlin",
                    "country": "Germany",
                    "url": "https://apply.workable.com/example-team/j/job-777/",
                    "description": "<p>Own test strategy.</p>",
                    "requirements": "<ul><li>Strong Python</li></ul>",
                    "benefits": "<p>Remote budget.</p>",
                },
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url("https://apply.workable.com/example-team/j/job-777/")

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="workable",
        company_slug="example-team",
        company_name="Example Team",
        job_id="job-777",
        title="Staff Quality Engineer",
        location="Berlin, Germany",
        url="https://apply.workable.com/example-team/j/job-777/",
        description="<p>Own test strategy.</p>\n<ul><li>Strong Python</li></ul>\n<p>Remote budget.</p>",
        posted_at=None,
        fetched_at=result.fetched_at,
    )


def test_fetch_job_from_url_uses_smartrecruiters_resolver_for_normalized_raw_job():
    smartrecruiters_job_id = "sr-job-12345"

    class _FakeResponse:
        def __init__(self, *, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None):
            assert url == f"https://api.smartrecruiters.com/v1/companies/example-team/postings/{smartrecruiters_job_id}"
            return _FakeResponse(
                status_code=200,
                payload={
                    "id": smartrecruiters_job_id,
                    "name": "Staff Quality Engineer",
                    "ref": f"https://jobs.smartrecruiters.com/example-team/{smartrecruiters_job_id}",
                    "releasedDate": "2026-04-18T10:00:00Z",
                    "location": {
                        "city": "Example City",
                        "country": "Exampleland",
                    },
                    "jobAd": {
                        "sections": "<p>Build resilient test systems.</p>",
                    },
                },
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url(f"https://jobs.smartrecruiters.com/example-team/{smartrecruiters_job_id}")

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="smartrecruiters",
        company_slug="example-team",
        company_name="Example Team",
        job_id=smartrecruiters_job_id,
        title="Staff Quality Engineer",
        location="Example City, Exampleland",
        url=f"https://jobs.smartrecruiters.com/example-team/{smartrecruiters_job_id}",
        description="<p>Build resilient test systems.</p>",
        posted_at="2026-04-18T10:00:00Z",
        fetched_at=result.fetched_at,
    )
