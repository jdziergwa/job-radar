import asyncio

import httpx
import pytest

from src.providers.hackernews import _parse_job_comment
from src.providers.remotive import _parse_remotive_job
from src.providers.remoteok import _parse_remoteok_job
from src.providers.himalayas import HimalayasProvider, _parse_himalayas_job


def test_parse_remotive_job_normalizes_html_and_salary():
    job = _parse_remotive_job(
        {
            "id": 42,
            "company_name": "Acme",
            "title": "Senior QA Engineer",
            "candidate_required_location": "Europe",
            "url": "https://remotive.com/remote-jobs/software-dev/senior-qa-engineer-42",
            "description": "<p>Own test automation and quality strategy.</p>",
            "publication_date": "2026-04-08T00:00:00Z",
            "salary": "€80,000 - €100,000",
        },
        "2026-04-09T00:00:00Z",
    )

    assert job.ats_platform == "remotive"
    assert job.company_slug == "acme"
    assert job.description == "Own test automation and quality strategy."
    assert job.salary_min == 80000
    assert job.salary_max == 100000
    assert job.salary_currency == "EUR"


def test_parse_remoteok_job_skips_non_job_metadata_rows():
    assert _parse_remoteok_job({"legal": "metadata"}, "2026-04-09T00:00:00Z") is None


def test_parse_remoteok_job_normalizes_defaults_and_html():
    job = _parse_remoteok_job(
        {
            "id": 77,
            "company": "Example Corp",
            "position": "SDET",
            "url": "https://remoteok.com/remote-jobs/77",
            "description": "<div><p>Lead automation for distributed systems.</p></div>",
        },
        "2026-04-09T00:00:00Z",
    )

    assert job is not None
    assert job.company_slug == "example-corp"
    assert job.location == "Remote"
    assert job.description == "Lead automation for distributed systems."


def test_parse_hackernews_comment_extracts_header_salary_and_url():
    job = _parse_job_comment(
        {
            "id": 123,
            "author": "founder1",
            "created_at": "2026-04-08T00:00:00Z",
            "text": (
                "Acme | Senior SDET | Remote (EU) | $140k-$170k "
                '<a href="https://jobs.acme.com/roles/sdet">Apply</a>'
            ),
        },
        "2026-04-09T00:00:00Z",
    )

    assert job is not None
    assert job.company_name == "Acme"
    assert job.title == "Senior SDET"
    assert job.location == "Remote (EU)"
    assert job.url == "https://jobs.acme.com/roles/sdet"
    assert job.salary_min == 140000
    assert job.salary_max == 170000


def test_parse_hackernews_comment_skips_candidate_posts():
    job = _parse_job_comment(
        {
            "id": 124,
            "author": "jobseeker1",
            "created_at": "2026-04-08T00:00:00Z",
            "text": "Looking for work | SDET | Remote | 10 years of experience testing distributed systems.",
        },
        "2026-04-09T00:00:00Z",
    )

    assert job is None


# ── Himalayas ──────────────────────────────────────────────────────────


def test_parse_himalayas_job_normalizes_html_and_salary():
    job = _parse_himalayas_job(
        {
            "guid": "https://himalayas.app/companies/acme/jobs/senior-sdet-12345",
            "companyName": "Acme Corp",
            "companySlug": "acme-corp",
            "title": "Senior SDET",
            "locationRestrictions": ["Europe", "USA"],
            "applicationLink": "https://jobs.acme.com/apply/sdet",
            "description": "<p>Own test automation and quality.</p>",
            "pubDate": "2026-04-08T00:00:00Z",
            "minSalary": 80000,
            "maxSalary": 110000,
            "currency": "USD",
        },
        "2026-04-09T00:00:00Z",
    )

    assert job.ats_platform == "himalayas"
    assert job.company_slug == "acme-corp"
    assert job.company_name == "Acme Corp"
    assert job.title == "Senior SDET"
    assert job.location == "Europe, USA"
    assert job.url == "https://jobs.acme.com/apply/sdet"
    assert "<" not in job.description
    assert "Own test automation" in job.description
    assert job.salary_min == 80000
    assert job.salary_max == 110000
    assert job.salary_currency == "USD"


def test_himalayas_fetch_returns_empty_on_http_error():
    import unittest.mock as mock

    async def _run():
        provider = HimalayasProvider()
        with mock.patch("httpx.AsyncClient") as mock_client:
            instance = mock_client.return_value.__aenter__.return_value
            instance.get.side_effect = httpx.ConnectError("simulated")
            return await provider.fetch_jobs(ctx=None)

    assert asyncio.run(_run()) == []

