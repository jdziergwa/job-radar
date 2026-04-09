from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import certifi
import httpx

from src.models import RawJob

if TYPE_CHECKING:
    from src.providers import ProviderContext, ProgressCallback

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
ADZUNA_REQUEST_TIMEOUT = 20
ADZUNA_DAILY_BUDGET = 250
ADZUNA_BUDGET_BUFFER_RATIO = 0.9
ADZUNA_RESULTS_PER_PAGE = 50
ADZUNA_MAX_PAGES_PER_QUERY = 5
ADZUNA_REQUEST_DELAY_SECONDS = 2.0

DEFAULT_SEARCH_TERMS = [
    "sdet",
    "qa engineer",
    "test automation engineer",
    "software engineer in test",
    "quality engineer",
]
DEFAULT_COUNTRIES = ["gb"]

COUNTRY_HINTS = {
    "uk": "gb",
    "united kingdom": "gb",
    "germany": "de",
    "deutschland": "de",
    "poland": "pl",
    "netherlands": "nl",
    "spain": "es",
    "portugal": "pt",
    "france": "fr",
    "ireland": "ie",
    "italy": "it",
    "switzerland": "ch",
}
COUNTRY_CURRENCY = {
    "gb": "GBP",
    "de": "EUR",
    "nl": "EUR",
    "pl": "PLN",
    "es": "EUR",
    "pt": "EUR",
    "fr": "EUR",
    "ie": "EUR",
    "it": "EUR",
    "ch": "CHF",
    "us": "USD",
    "ca": "CAD",
}


def _should_stop_for_budget(
    request_count: int,
    daily_budget: int = ADZUNA_DAILY_BUDGET,
    buffer_ratio: float = ADZUNA_BUDGET_BUFFER_RATIO,
) -> bool:
    return request_count >= int(daily_budget * buffer_ratio)


def _clean_regex_pattern(pattern: str) -> list[str]:
    text = (pattern or "").lower()
    text = text.replace(r"\b", "")
    text = text.replace(r"\s+", " ")
    text = text.replace(r"\s*", " ")
    text = text.replace(r"\-", "-")
    text = text.replace("(", "").replace(")", "")
    text = re.sub(r"[\[\]{}^$?+*]", " ", text)

    candidates = [part.strip() for part in text.split("|")]
    cleaned: list[str] = []
    for candidate in candidates:
        phrase = " ".join(re.sub(r"[^a-z0-9\- ]+", " ", candidate).split()).strip()
        if len(phrase) >= 3 and any(ch.isalpha() for ch in phrase):
            cleaned.append(phrase)
    return cleaned


def _derive_search_terms(config: dict[str, Any]) -> list[str]:
    provider_settings = (config.get("providers", {}) or {}).get("adzuna", {}) if isinstance(config.get("providers", {}), dict) else {}
    explicit_terms = provider_settings.get("search_terms") if isinstance(provider_settings, dict) else None
    if isinstance(explicit_terms, list):
        values = [str(value).strip() for value in explicit_terms if str(value).strip()]
        if values:
            return values

    keywords = config.get("keywords", {}) if isinstance(config.get("keywords", {}), dict) else {}
    title_patterns = keywords.get("title_patterns", {}) if isinstance(keywords.get("title_patterns", {}), dict) else {}
    terms: list[str] = []

    for key in ("high_confidence", "broad"):
        patterns = title_patterns.get(key, [])
        if not isinstance(patterns, list):
            continue
        for pattern in patterns:
            if not isinstance(pattern, str):
                continue
            for term in _clean_regex_pattern(pattern):
                if term not in terms:
                    terms.append(term)

    return terms[:6] or DEFAULT_SEARCH_TERMS


def _derive_country_codes(config: dict[str, Any]) -> list[str]:
    provider_settings = (config.get("providers", {}) or {}).get("adzuna", {}) if isinstance(config.get("providers", {}), dict) else {}
    explicit_countries = provider_settings.get("countries") if isinstance(provider_settings, dict) else None
    if isinstance(explicit_countries, list):
        values = [str(value).strip().lower() for value in explicit_countries if str(value).strip()]
        if values:
            return values

    keywords = config.get("keywords", {}) if isinstance(config.get("keywords", {}), dict) else {}
    location_patterns = keywords.get("location_patterns", []) if isinstance(keywords.get("location_patterns", []), list) else []
    combined = " ".join(location_patterns).lower()

    countries: list[str] = []
    for hint, code in COUNTRY_HINTS.items():
        if hint in combined and code not in countries:
            countries.append(code)

    return countries or DEFAULT_COUNTRIES


def _adzuna_runtime_settings(config: dict[str, Any]) -> tuple[int, float, int]:
    provider_settings = (config.get("providers", {}) or {}).get("adzuna", {}) if isinstance(config.get("providers", {}), dict) else {}
    runtime_settings = config.get("runtime", {}) if isinstance(config.get("runtime", {}), dict) else {}

    daily_budget = int(provider_settings.get("daily_budget", ADZUNA_DAILY_BUDGET)) if isinstance(provider_settings, dict) else ADZUNA_DAILY_BUDGET
    max_pages = int(provider_settings.get("max_pages_per_query", ADZUNA_MAX_PAGES_PER_QUERY)) if isinstance(provider_settings, dict) else ADZUNA_MAX_PAGES_PER_QUERY
    delay_seconds = float(provider_settings.get("delay_seconds", ADZUNA_REQUEST_DELAY_SECONDS)) if isinstance(provider_settings, dict) else ADZUNA_REQUEST_DELAY_SECONDS

    if runtime_settings.get("slow_mode"):
        max_pages = min(max_pages, 3)
        delay_seconds = max(delay_seconds, 3.0)

    return daily_budget, delay_seconds, max_pages


def _parse_adzuna_job(item: dict[str, object], country: str, fetched_at: str) -> RawJob:
    company = item.get("company", {})
    location = item.get("location", {})

    company_name = str(company.get("display_name") if isinstance(company, dict) else "Unknown")
    title = str(item.get("title") or "").strip()
    job_id = str(item.get("id") or item.get("__CLASS__") or item.get("redirect_url") or "")
    url = str(item.get("redirect_url") or item.get("adref") or "")

    salary_min = item.get("salary_min")
    salary_max = item.get("salary_max")
    salary_currency = COUNTRY_CURRENCY.get(country.lower())

    return RawJob(
        ats_platform="adzuna",
        company_slug=re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-") or "unknown",
        company_name=company_name,
        job_id=job_id or url,
        title=title,
        location=str(location.get("display_name") if isinstance(location, dict) else ""),
        url=url,
        description=str(item.get("description") or ""),
        posted_at=str(item.get("created")) if item.get("created") is not None else None,
        fetched_at=fetched_at,
        salary_min=int(salary_min) if isinstance(salary_min, (int, float)) else None,
        salary_max=int(salary_max) if isinstance(salary_max, (int, float)) else None,
        salary_currency=salary_currency,
    )


class AdzunaProvider:
    name = "adzuna"
    display_name = "Adzuna"
    description = "Official Adzuna API source. Requires ADZUNA_APP_ID and ADZUNA_APP_KEY."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        app_id = os.getenv("ADZUNA_APP_ID")
        app_key = os.getenv("ADZUNA_APP_KEY")
        if not app_id or not app_key:
            logger.info("Adzuna: ADZUNA_APP_ID/ADZUNA_APP_KEY not configured; skipping")
            return []

        config = ctx.config if isinstance(ctx.config, dict) else {}
        search_terms = _derive_search_terms(config)
        countries = _derive_country_codes(config)
        daily_budget, delay_seconds, max_pages_per_query = _adzuna_runtime_settings(config)
        budget_limit = int(daily_budget * ADZUNA_BUDGET_BUFFER_RATIO)

        ssl_context = certifi.where()
        now = datetime.now(timezone.utc).isoformat()
        raw_jobs: list[RawJob] = []
        request_count = 0
        total_queries = max(1, len(search_terms) * len(countries))
        completed_queries = 0

        async with httpx.AsyncClient(verify=ssl_context) as client:
            for country in countries:
                for term in search_terms:
                    completed_queries += 1

                    for page in range(1, max_pages_per_query + 1):
                        if _should_stop_for_budget(request_count, daily_budget):
                            logger.warning(
                                "Adzuna: approaching daily budget (%d/%d), stopping early",
                                request_count,
                                budget_limit,
                            )
                            return raw_jobs

                        url = f"{ADZUNA_BASE_URL}/{country}/search/{page}"
                        params = {
                            "app_id": app_id,
                            "app_key": app_key,
                            "results_per_page": ADZUNA_RESULTS_PER_PAGE,
                            "what": term,
                            "content-type": "application/json",
                            "sort_by": "date",
                        }

                        try:
                            resp = await client.get(url, params=params, timeout=ADZUNA_REQUEST_TIMEOUT)
                            resp.raise_for_status()
                            payload = resp.json()
                        except Exception as exc:
                            logger.warning("Adzuna fetch failed for %s/%s page %d: %s", country, term, page, exc)
                            break

                        request_count += 1

                        results = payload.get("results", [])
                        if not isinstance(results, list) or not results:
                            break

                        for item in results:
                            if isinstance(item, dict):
                                raw_jobs.append(_parse_adzuna_job(item, country, now))

                        if progress_callback:
                            progress_callback(completed_queries, total_queries)

                        await asyncio.sleep(delay_seconds)

        logger.info("Adzuna: Fetched %d jobs in %d requests", len(raw_jobs), request_count)
        return raw_jobs
