from src.providers.hackernews import _parse_job_comment
from src.providers.remotive import _parse_remotive_job
from src.providers.remoteok import _parse_remoteok_job


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
