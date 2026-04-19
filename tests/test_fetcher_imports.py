import asyncio
from unittest import mock

from src import fetcher
from src.models import CandidateJob, RawJob


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


def test_fetch_job_from_url_supports_job_boards_greenhouse_host():
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
            assert url == "https://boards-api.greenhouse.io/v1/boards/reddit/jobs/7488992"
            return _FakeResponse(
                status_code=200,
                payload={
                    "id": 7488992,
                    "title": "Platform Quality Engineer",
                    "absolute_url": "https://job-boards.greenhouse.io/reddit/jobs/7488992",
                    "updated_at": "2026-04-19T10:00:00Z",
                    "location": {"name": "Remote"},
                    "content": "<p>Build reliable internal systems.</p>",
                },
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url("https://job-boards.greenhouse.io/reddit/jobs/7488992")

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="greenhouse",
        company_slug="reddit",
        company_name="Reddit",
        job_id="7488992",
        title="Platform Quality Engineer",
        location="Remote",
        url="https://job-boards.greenhouse.io/reddit/jobs/7488992",
        description="<p>Build reliable internal systems.</p>",
        posted_at="2026-04-19T10:00:00Z",
        fetched_at=result.fetched_at,
    )


def test_fetch_job_from_url_uses_bamboohr_resolver_for_normalized_raw_job():
    class _FakeResponse:
        def __init__(self, *, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None, follow_redirects=None, headers=None):
            assert url == "https://example-team.bamboohr.com/careers/155/detail"
            return _FakeResponse(
                status_code=200,
                text="""
                {
                  "result": {
                    "jobOpening": {
                      "jobOpeningName": "Senior Software Engineer in Test",
                      "description": "<p>Own release quality and test automation.</p>",
                      "datePosted": "2026-04-19",
                      "locationType": "1",
                      "location": {
                        "city": null,
                        "state": null,
                        "addressCountry": null
                      },
                      "atsLocation": {
                        "city": null,
                        "state": null,
                        "country": null
                      }
                    }
                  }
                }
                """,
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url("https://example-team.bamboohr.com/careers/155")

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="bamboohr",
        company_slug="example-team",
        company_name="Example Team",
        job_id="155",
        title="Senior Software Engineer in Test",
        location="Remote",
        url="https://example-team.bamboohr.com/careers/155",
        description="<p>Own release quality and test automation.</p>",
        posted_at="2026-04-19",
        fetched_at=result.fetched_at,
        location_metadata={
            "workplace_type": "Remote",
            "raw_location": "Remote",
        },
    )


def test_fetch_job_from_url_uses_bamboohr_detail_page_markup_when_available():
    class _FakeResponse:
        def __init__(self, *, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None, follow_redirects=None, headers=None):
            assert url == "https://example-team.bamboohr.com/careers/155/detail"
            return _FakeResponse(
                status_code=200,
                text="""
                <html>
                    <body>
                        <main>
                            <h1>Senior Quality Engineer</h1>
                            <div>
                                <p>About Example Team</p>
                                <p>Build quality systems across connected experiences.</p>
                            </div>
                            <div>
                                <p>Location</p>
                                <p>Remote</p>
                            </div>
                            <div>
                                <p>Department</p>
                                <p>Quality Engineering</p>
                            </div>
                        </main>
                    </body>
                </html>
                """,
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url("https://example-team.bamboohr.com/careers/155")

    result = asyncio.run(_run())

    assert result is not None
    assert result.ats_platform == "bamboohr"
    assert result.company_slug == "example-team"
    assert result.company_name == "Example Team"
    assert result.job_id == "155"
    assert result.title == "Senior Quality Engineer"
    assert result.location == "Remote"
    assert result.url == "https://example-team.bamboohr.com/careers/155"
    assert "Build quality systems across connected experiences." in result.description
    assert "Department" in result.description
    assert result.posted_at is None
    assert result.location_metadata == {
        "raw_location": "Remote",
    }


def test_fetch_job_from_url_uses_bamboohr_meta_description_fallback():
    class _FakeResponse:
        def __init__(self, *, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None, follow_redirects=None, headers=None):
            if url == "https://example-team.bamboohr.com/careers/155/detail":
                return _FakeResponse(status_code=404, text="")
            assert url == "https://example-team.bamboohr.com/careers/155"
            return _FakeResponse(
                status_code=200,
                text="""
                <html>
                    <head>
                        <meta property="og:title" content="Senior Quality Engineer" />
                        <meta property="og:description" content="Build product quality systems across connected experiences." />
                    </head>
                    <body><div id="poRoot"></div></body>
                </html>
                """,
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url("https://example-team.bamboohr.com/careers/155")

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="bamboohr",
        company_slug="example-team",
        company_name="Example Team",
        job_id="155",
        title="Senior Quality Engineer",
        location="",
        url="https://example-team.bamboohr.com/careers/155",
        description="Build product quality systems across connected experiences.",
        posted_at=None,
        fetched_at=result.fetched_at,
        location_metadata={},
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


def test_fetch_job_from_url_supports_regional_lever_host():
    lever_job_id = "11111111-2222-4333-8444-555555555555"

    class _FakeResponse:
        def __init__(self, *, status_code: int, payload: dict | None = None, text: str = ""):
            self.status_code = status_code
            self._payload = payload
            self.text = text

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None, follow_redirects=None):
            if url == f"https://api.lever.co/v0/postings/example-team/{lever_job_id}":
                return _FakeResponse(
                    status_code=404,
                    payload={"ok": False, "error": "Document not found"},
                )

            assert url == f"https://jobs.eu.lever.co/example-team/{lever_job_id}"
            return _FakeResponse(
                status_code=200,
                text="""
                <html>
                  <head>
                    <meta property="og:title" content="Example Team Careers - Staff Quality Engineer" />
                  </head>
                  <body>
                    <div class="posting-category location">
                      Example City /<span> Example Region /</span><span> Remote</span>
                    </div>
                    <div class="posting-category workplaceTypes">Hybrid</div>
                    <script type="application/ld+json">
                      {
                        "@context": "http://schema.org",
                        "@type": "JobPosting",
                        "title": "Staff Quality Engineer",
                        "datePosted": "2026-03-11",
                        "description": "<p>Build quality systems at scale.</p>",
                        "jobLocation": [
                          {"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Example Region"}},
                          {"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Remote"}},
                          {"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Example City"}}
                        ]
                      }
                    </script>
                  </body>
                </html>
                """,
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url(
                f"https://jobs.eu.lever.co/example-team/{lever_job_id}?lever-origin=applied&lever-source%5B%5D=TestSource"
            )

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="lever",
        company_slug="example-team",
        company_name="Example Team",
        job_id=lever_job_id,
        title="Staff Quality Engineer",
        location="Example City / Example Region / Remote",
        url=f"https://jobs.eu.lever.co/example-team/{lever_job_id}",
        description="<p>Build quality systems at scale.</p>",
        posted_at="2026-03-11",
        fetched_at=result.fetched_at,
        location_metadata={
            "raw_location": "Example City / Example Region / Remote",
            "workplace_type": "Hybrid",
        },
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


def test_fetch_job_from_url_uses_workday_resolver_for_normalized_raw_job():
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
            assert (
                url
                == "https://exampleco.wd12.myworkdayjobs.com/wday/cxs/exampleco/ExampleBoard/job/Remote/Staff-Quality-Engineer_R-12345-1"
            )
            return _FakeResponse(
                status_code=200,
                payload={
                    "jobPostingInfo": {
                        "title": "Staff Quality Engineer",
                        "jobDescription": "<p>Drive quality strategy across product surfaces.</p>",
                        "location": "London",
                        "startDate": "2026-04-19",
                        "remoteType": "Hybrid",
                        "externalUrl": "https://exampleco.wd12.myworkdayjobs.com/ExampleBoard/job/Remote/Staff-Quality-Engineer_R-12345-1",
                    },
                    "hiringOrganization": {
                        "name": "Example Co",
                    },
                },
            )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            return await fetcher.fetch_job_from_url(
                "https://exampleco.wd12.myworkdayjobs.com/en-US/ExampleBoard/job/Remote/Staff-Quality-Engineer_R-12345-1"
            )

    result = asyncio.run(_run())

    assert result == RawJob(
        ats_platform="workday",
        company_slug="exampleco",
        company_name="Example Co",
        job_id="Staff-Quality-Engineer_R-12345-1",
        title="Staff Quality Engineer",
        location="London",
        url="https://exampleco.wd12.myworkdayjobs.com/ExampleBoard/job/Remote/Staff-Quality-Engineer_R-12345-1",
        description="<p>Drive quality strategy across product surfaces.</p>",
        posted_at="2026-04-19",
        fetched_at=result.fetched_at,
        location_metadata={
            "raw_location": "London",
            "workplace_type": "Hybrid",
        },
    )


def test_populate_descriptions_applies_supported_ats_richer_fields():
    class _FakeResponse:
        def __init__(self, *, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, timeout=None, follow_redirects=None, headers=None):
            assert url == "https://example-team.bamboohr.com/careers/155/detail"
            return _FakeResponse(
                status_code=200,
                text="""
                {
                  "result": {
                    "jobOpening": {
                      "jobOpeningName": "Senior Quality Engineer",
                      "description": "<p>Build quality systems across connected experiences.</p>",
                      "datePosted": "2026-04-19",
                      "locationType": "1",
                      "location": {
                        "city": null,
                        "state": null,
                        "addressCountry": null
                      },
                      "atsLocation": {
                        "city": null,
                        "state": null,
                        "country": null
                      }
                    }
                  }
                }
                """,
            )

    candidate = CandidateJob(
        db_id=1,
        ats_platform="bamboohr",
        company_slug="example-team",
        company_name="Example Team",
        job_id="155",
        title="Example Team",
        location="",
        url="https://example-team.bamboohr.com/careers/155",
        description="short stub",
        posted_at=None,
        first_seen_at="2026-04-19T10:00:00Z",
    )

    async def _run():
        with mock.patch("src.fetcher.httpx.AsyncClient", _FakeAsyncClient):
            hydrated = await fetcher.populate_descriptions([candidate])
            return hydrated[0]

    result = asyncio.run(_run())

    assert result.title == "Senior Quality Engineer"
    assert result.location == "Remote"
    assert result.description == "<p>Build quality systems across connected experiences.</p>"
    assert result.posted_at == "2026-04-19"
    assert result.location_metadata == {
        "workplace_type": "Remote",
        "raw_location": "Remote",
    }
