import asyncio

import httpx
import pytest

from src.providers.hackernews import _parse_job_comment
from src.providers.remotive import _parse_remotive_job
from src.providers.remoteok import _parse_remoteok_job
from src.providers.himalayas import HimalayasProvider, _parse_himalayas_job
from src.providers.jobicy import JobicyProvider, _parse_jobicy_job, _rfc2822_to_iso


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


# ── Jobicy ─────────────────────────────────────────────────────────────


def test_rfc2822_to_iso_converts_correctly():
    result = _rfc2822_to_iso("Mon, 08 Apr 2026 12:00:00 +0000")
    assert result is not None
    assert result.startswith("2026-04-08")
    assert "T" in result


def test_rfc2822_to_iso_returns_none_for_none():
    assert _rfc2822_to_iso(None) is None


def test_parse_jobicy_job_handles_html_and_rfc2822_date():
    job = _parse_jobicy_job(
        {
            "id": 9999,
            "companyName": "Remote Co",
            "jobTitle": "QA Lead",
            "jobGeo": "Worldwide",
            "url": "https://jobicy.com/jobs/9999-qa-lead",
            "jobDescription": "<p>Lead the <strong>QA</strong> team globally.</p>",
            "pubDate": "Mon, 08 Apr 2026 10:00:00 +0000",
            "annualSalaryMin": 70000,
            "annualSalaryMax": 90000,
            "salaryCurrency": "USD",
        },
        "2026-04-09T00:00:00Z",
    )

    assert job.ats_platform == "jobicy"
    assert job.company_slug == "remote-co"
    assert job.job_id == "9999"
    assert job.title == "QA Lead"
    assert job.location == "Worldwide"
    assert "<" not in job.description
    assert "Lead the" in job.description
    assert job.posted_at is not None
    assert job.posted_at.startswith("2026-04-08")
    assert job.salary_min == 70000
    assert job.salary_max == 90000
    assert job.salary_currency == "USD"


def test_jobicy_fetch_returns_empty_on_http_error():
    import unittest.mock as mock

    async def _run():
        provider = JobicyProvider()
        with mock.patch("httpx.AsyncClient") as mock_client:
            instance = mock_client.return_value.__aenter__.return_value
            instance.get.side_effect = httpx.ConnectError("simulated")
            return await provider.fetch_jobs(ctx=None)

    assert asyncio.run(_run()) == []
