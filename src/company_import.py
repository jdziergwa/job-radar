"""Helpers for importing ATS company registries from external datasets."""

from __future__ import annotations

import json
import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

import certifi
import yaml


SUPPORTED_PLATFORMS = ("greenhouse", "lever", "ashby", "workable", "bamboohr", "smartrecruiters")

PLATFORM_ALIASES = {
    "greenhouse": "greenhouse",
    "gh": "greenhouse",
    "lever": "lever",
    "ashby": "ashby",
    "ashbyhq": "ashby",
    "workable": "workable",
    "bamboohr": "bamboohr",
    "smartrecruiters": "smartrecruiters",
    "sr": "smartrecruiters",
}

URL_PATTERNS = (
    ("greenhouse", re.compile(r"https?://(?:boards(?:-api)?\.greenhouse\.io/(?:v1/boards/)?|[^/]+/jobs/search\?gh_jid=)(?P<slug>[a-z0-9\-]+)?", re.IGNORECASE)),
    ("lever", re.compile(r"https?://(?:jobs|api)\.lever\.co/(?:v0/postings/)?(?P<slug>[a-z0-9\-]+)", re.IGNORECASE)),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/(?P<slug>[a-z0-9\-]+)", re.IGNORECASE)),
    ("workable", re.compile(r"https?://apply\.workable\.com/(?P<slug>[a-z0-9\-]+)", re.IGNORECASE)),
    ("bamboohr", re.compile(r"https?://(?P<slug>[a-z0-9\-]+)\.bamboohr\.com", re.IGNORECASE)),
    ("smartrecruiters", re.compile(r"https?://(?:jobs|careers|api)\.smartrecruiters\.com/(?:v1/companies/)?(?P<slug>[a-z0-9\-]+)?", re.IGNORECASE)),
)

_ssl_ctx = ssl.create_default_context(cafile=certifi.where())


@dataclass(frozen=True)
class ImportedCompany:
    platform: str
    slug: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "name": self.name}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def extract_platform_slug_from_url(url: str, fallback_slug: str | None = None) -> tuple[str | None, str | None]:
    normalized_fallback = _slugify(fallback_slug) if fallback_slug else None

    for platform, pattern in URL_PATTERNS:
        match = pattern.search(url)
        if match:
            slug = match.groupdict().get("slug") or normalized_fallback
            if slug:
                return platform, _slugify(slug)

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and path_parts:
        return "greenhouse", _slugify(path_parts[0])
    if host == "jobs.lever.co" and path_parts:
        return "lever", _slugify(path_parts[0])
    if host == "jobs.ashbyhq.com" and path_parts:
        return "ashby", _slugify(path_parts[0])
    if host == "apply.workable.com" and path_parts:
        return "workable", _slugify(path_parts[0])
    if host.endswith(".bamboohr.com"):
        return "bamboohr", _slugify(host.split(".")[0])

    return None, normalized_fallback


def _normalize_platform(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    for alias, normalized in PLATFORM_ALIASES.items():
        if alias == lowered or alias in lowered:
            return normalized
    return None


def _extract_urls(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.startswith("http://") or value.startswith("https://") else []
    if isinstance(value, list):
        urls: list[str] = []
        for item in value:
            urls.extend(_extract_urls(item))
        return urls
    if isinstance(value, dict):
        urls: list[str] = []
        for item in value.values():
            urls.extend(_extract_urls(item))
        return urls
    return []


def _extract_name(record: dict[str, Any]) -> str | None:
    for key in ("name", "company_name", "companyName", "company"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_explicit_slug(record: dict[str, Any]) -> str | None:
    for key in ("slug", "company_slug", "companySlug", "ats_slug", "atsSlug"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return _slugify(value)
    return None


def _extract_slug_from_scraping_config(record: dict[str, Any]) -> str | None:
    config = record.get("scrapingConfig")
    if not isinstance(config, dict):
        return None

    config_url = config.get("url")
    if isinstance(config_url, str) and config_url.strip():
        for _, pattern in URL_PATTERNS:
            match = pattern.search(config_url)
            if match:
                slug = match.groupdict().get("slug")
                if slug:
                    return _slugify(slug)

    config_id = config.get("id")
    if isinstance(config_id, str) and config_id.strip():
        return _slugify(config_id)

    return None


def _extract_platform_from_record(record: dict[str, Any]) -> tuple[str | None, str | None]:
    explicit_slug = _extract_explicit_slug(record)
    config_slug = _extract_slug_from_scraping_config(record)
    record_id = record.get("id")
    fallback_slug = explicit_slug or config_slug

    if not fallback_slug and isinstance(record_id, str) and record_id.strip():
        fallback_slug = _slugify(record_id)

    for key in (
        "platform",
        "provider",
        "ats",
        "job_board",
        "jobBoard",
        "board",
        "jobBoardProvider",
        "scrapingStrategy",
    ):
        value = record.get(key)
        if isinstance(value, dict):
            nested_platform, nested_slug = _extract_platform_from_record(value)
            if nested_platform:
                return nested_platform, nested_slug or fallback_slug
        normalized = _normalize_platform(value)
        if normalized:
            return normalized, fallback_slug

    urls = _extract_urls(record)
    for url in urls:
        platform, slug = extract_platform_slug_from_url(url, fallback_slug=fallback_slug)
        if platform and slug:
            return platform, slug

    return None, fallback_slug


def normalize_company_record(record: dict[str, Any]) -> ImportedCompany | None:
    name = _extract_name(record)
    if not name:
        return None

    platform, slug = _extract_platform_from_record(record)
    if not platform or platform not in SUPPORTED_PLATFORMS:
        return None

    slug = slug or _slugify(name)
    if not slug:
        return None

    return ImportedCompany(platform=platform, slug=slug, name=name)


def extract_candidate_records(payload: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return

        if isinstance(value, dict):
            if _extract_name(value):
                candidates.append(value)
            for nested in value.values():
                walk(nested)

    walk(payload)
    return candidates


def import_companies_from_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    deduped: dict[str, dict[str, dict[str, str]]] = {platform: {} for platform in SUPPORTED_PLATFORMS}

    for record in records:
        normalized = normalize_company_record(record)
        if normalized is None:
            continue
        deduped[normalized.platform][normalized.slug] = normalized.to_dict()

    return {
        platform: sorted(entries.values(), key=lambda item: item["name"].lower())
        for platform, entries in deduped.items()
        if entries
    }


def import_companies_from_payload(payload: Any) -> dict[str, list[dict[str, str]]]:
    return import_companies_from_records(extract_candidate_records(payload))


def dump_companies_yaml(companies: dict[str, list[dict[str, str]]]) -> str:
    return yaml.safe_dump(companies, sort_keys=False, allow_unicode=False)


def load_payload(input_path: str) -> Any:
    if input_path.startswith("http://") or input_path.startswith("https://"):
        context = _ssl_ctx if input_path.startswith("https://") else None
        with urlopen(input_path, context=context) as response:
            return json.loads(response.read().decode("utf-8"))

    path = Path(input_path)
    return json.loads(path.read_text(encoding="utf-8"))
