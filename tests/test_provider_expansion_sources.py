import asyncio

from src.providers.arbeitnow import ArbeitnowProvider, _parse_arbeitnow_job
from src.providers.weworkremotely import _parse_weworkremotely_feed, _split_title


def test_parse_arbeitnow_job_normalizes_fields():
    job = _parse_arbeitnow_job(
        {
            "slug": "senior-qa-engineer-123",
            "company_name": "Example GmbH",
            "title": "Senior QA Engineer",
            "location": "Berlin",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/senior-qa-engineer-123",
            "description": "<p>Own test automation and CI quality gates.</p>",
            "created_at": 1712620800,
        },
        "2026-04-09T00:00:00Z",
    )

    assert job.ats_platform == "arbeitnow"
    assert job.company_slug == "example-gmbh"
    assert job.job_id == "senior-qa-engineer-123"
    assert job.location == "Berlin"
    assert job.description == "Own test automation and CI quality gates."
    assert job.posted_at == "2024-04-09T00:00:00+00:00"


def test_arbeitnow_provider_fetches_paginated_results(monkeypatch):
    responses = {
        1: {
            "data": [
                {
                    "slug": "job-1",
                    "company_name": "Acme",
                    "title": "QA Engineer",
                    "location": "Berlin",
                    "url": "https://example.com/job-1",
                    "description": "<p>Job 1</p>",
                    "created_at": 1712620800,
                }
            ],
            "meta": {"current_page": 1},
            "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=2"},
        },
        2: {
            "data": [
                {
                    "slug": "job-2",
                    "company_name": "Beta",
                    "title": "SDET",
                    "location": "Remote Europe",
                    "url": "https://example.com/job-2",
                    "description": "<p>Job 2</p>",
                    "created_at": 1712707200,
                }
            ],
            "meta": {"current_page": 2},
            "links": {"next": None},
        },
    }

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None, timeout=None):
            return _FakeResponse(responses[params["page"]])

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("src.providers.arbeitnow.httpx.AsyncClient", lambda *args, **kwargs: _FakeClient())
    monkeypatch.setattr("src.providers.arbeitnow.asyncio.sleep", _no_sleep)

    progress = []
    jobs = asyncio.run(ArbeitnowProvider().fetch_jobs(
        ctx=None,
        progress_callback=lambda current, total: progress.append((current, total)),
    ))

    assert [job.job_id for job in jobs] == ["job-1", "job-2"]
    assert progress == [(1, 1), (2, 2)]


def test_split_title_handles_company_prefix():
    company, title = _split_title("Example Inc: Senior QA Engineer")

    assert company == "Example Inc"
    assert title == "Senior QA Engineer"


def test_parse_weworkremotely_feed_extracts_items():
    xml_text = """\
<rss version="2.0">
  <channel>
    <item>
      <title>Example Inc: Senior QA Engineer</title>
      <link>https://weworkremotely.com/remote-jobs/example-inc-senior-qa-engineer</link>
      <guid>wwr-1</guid>
      <pubDate>Tue, 09 Apr 2024 12:00:00 GMT</pubDate>
      <description><![CDATA[<p>Lead quality engineering for our remote platform.</p>]]></description>
    </item>
  </channel>
</rss>
"""

    jobs = _parse_weworkremotely_feed(xml_text, "2026-04-09T00:00:00Z")

    assert len(jobs) == 1
    assert jobs[0].ats_platform == "weworkremotely"
    assert jobs[0].company_name == "Example Inc"
    assert jobs[0].company_slug == "example-inc"
    assert jobs[0].title == "Senior QA Engineer"
    assert jobs[0].location == "Remote"
    assert jobs[0].job_id == "wwr-1"
    assert jobs[0].description == "Lead quality engineering for our remote platform."
