import asyncio

from src.providers.adzuna import (
    AdzunaProvider,
    _derive_country_codes,
    _derive_search_terms,
    _parse_adzuna_job,
    _should_stop_for_budget,
)
from src.providers import local_ats
from src.main import build_parser


def test_parse_adzuna_job_maps_core_fields():
    job = _parse_adzuna_job(
        {
            "id": "12345",
            "title": "Senior QA Engineer",
            "redirect_url": "https://example.com/jobs/12345",
            "description": "Lead quality engineering across the platform.",
            "created": "2026-04-10T10:00:00Z",
            "salary_min": 70000,
            "salary_max": 90000,
            "company": {"display_name": "Example Ltd"},
            "location": {"display_name": "London"},
        },
        "gb",
        "2026-04-10T12:00:00Z",
    )

    assert job.ats_platform == "adzuna"
    assert job.company_slug == "example-ltd"
    assert job.title == "Senior QA Engineer"
    assert job.location == "London"
    assert job.salary_min == 70000
    assert job.salary_max == 90000
    assert job.salary_currency == "GBP"


def test_adzuna_provider_returns_empty_without_credentials(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    jobs = asyncio.run(AdzunaProvider().fetch_jobs(
        ctx=type("Ctx", (), {"config": {}, "companies": {}, "profile_dir": None})(),
        progress_callback=None,
    ))

    assert jobs == []


def test_should_stop_for_budget_respects_buffer():
    assert _should_stop_for_budget(224, daily_budget=250) is False
    assert _should_stop_for_budget(225, daily_budget=250) is True


def test_derive_search_terms_prefers_configured_terms():
    config = {
        "providers": {
            "adzuna": {
                "search_terms": ["qa engineer", "sdet"],
            }
        }
    }

    assert _derive_search_terms(config) == ["qa engineer", "sdet"]


def test_derive_country_codes_reads_location_hints():
    config = {
        "keywords": {
            "location_patterns": [
                r"\b(germany|deutschland|berlin)\b",
                r"\b(poland|warsaw|krakow)\b",
                r"\b(uk|united kingdom)\b",
            ]
        }
    }

    assert _derive_country_codes(config) == ["gb", "de", "pl"]


def test_slow_mode_flag_is_parsed():
    parser = build_parser()
    args = parser.parse_args(["--slow", "--dry-run"])

    assert args.slow is True
    assert args.dry_run is True


def test_local_ats_slow_mode_reduces_concurrency_and_adds_delay():
    runtime_config = {"slow_mode": True}

    assert local_ats._platform_concurrency("greenhouse", runtime_config) == 2
    assert local_ats._platform_concurrency("lever", runtime_config) == 2
    assert local_ats._platform_delay("greenhouse", runtime_config) == 2.0
    assert local_ats._platform_delay("lever", runtime_config) == 2.0
