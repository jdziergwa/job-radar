"""Helpers for importing ATS company registries from external datasets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml


SUPPORTED_PLATFORMS = ("greenhouse", "lever", "ashby", "workable")

PLATFORM_ALIASES = {
    "greenhouse": "greenhouse",
    "gh": "greenhouse",
    "lever": "lever",
    "ashby": "ashby",
    "ashbyhq": "ashby",
    "workable": "workable",
}

URL_PATTERNS = (
    ("greenhouse", re.compile(r"https?://(?:boards(?:-api)?\.greenhouse\.io/(?:v1/boards/)?|[^/]+/jobs/search\?gh_jid=)(?P<slug>[a-z0-9\-]+)?", re.IGNORECASE)),
    ("lever", re.compile(r"https?://(?:jobs|api)\.lever\.co/(?:v0/postings/)?(?P<slug>[a-z0-9\-]+)", re.IGNORECASE)),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/(?P<slug>[a-z0-9\-]+)", re.IGNORECASE)),
    ("workable", re.compile(r"https?://apply\.workable\.com/(?P<slug>[a-z0-9\-]+)", re.IGNORECASE)),
)


@dataclass(frozen=True)
class ImportedCompany:
    platform: str
    slug: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "name": self.name}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


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


def _extract_platform_from_record(record: dict[str, Any]) -> tuple[str | None, str | None]:
    explicit_slug = _extract_explicit_slug(record)

    for key in ("platform", "provider", "ats", "job_board", "jobBoard", "board"):
        value = record.get(key)
        if isinstance(value, dict):
            nested_platform, nested_slug = _extract_platform_from_record(value)
            if nested_platform:
                return nested_platform, nested_slug or explicit_slug
        normalized = _normalize_platform(value)
        if normalized:
            return normalized, explicit_slug

    urls = _extract_urls(record)
    for url in urls:
        for platform, pattern in URL_PATTERNS:
            match = pattern.search(url)
            if match:
                slug = match.groupdict().get("slug") or explicit_slug
                if slug:
                    return platform, _slugify(slug)

        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path_parts = [part for part in parsed.path.split("/") if part]

        if host == "boards.greenhouse.io" and path_parts:
            return "greenhouse", _slugify(path_parts[0])
        if host == "jobs.lever.co" and path_parts:
            return "lever", _slugify(path_parts[0])
        if host == "jobs.ashbyhq.com" and path_parts:
            return "ashby", _slugify(path_parts[0])
        if host == "apply.workable.com" and path_parts:
            return "workable", _slugify(path_parts[0])

    return None, explicit_slug


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


def _iter_candidate_records(payload: Any) -> list[dict[str, Any]]:
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


def import_companies_from_payload(payload: Any) -> dict[str, list[dict[str, str]]]:
    deduped: dict[str, dict[str, dict[str, str]]] = {platform: {} for platform in SUPPORTED_PLATFORMS}

    for record in _iter_candidate_records(payload):
        normalized = normalize_company_record(record)
        if normalized is None:
            continue
        deduped[normalized.platform][normalized.slug] = normalized.to_dict()

    return {
        platform: sorted(entries.values(), key=lambda item: item["name"].lower())
        for platform, entries in deduped.items()
        if entries
    }


def dump_companies_yaml(companies: dict[str, list[dict[str, str]]]) -> str:
    return yaml.safe_dump(companies, sort_keys=False, allow_unicode=False)


def load_payload(input_path: str) -> Any:
    if input_path.startswith("http://") or input_path.startswith("https://"):
        with urlopen(input_path) as response:
            return json.loads(response.read().decode("utf-8"))

    path = Path(input_path)
    return json.loads(path.read_text(encoding="utf-8"))
