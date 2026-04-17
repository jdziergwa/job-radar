from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from src.company_import import extract_platform_slug_from_url
from src.providers.utils import slugify


@dataclass(frozen=True)
class ResolvedJobRef:
    url: str
    platform: str | None
    company_slug: str | None
    job_id: str | None


def detect_ats_platform(url: str) -> str | None:
    """Return the ATS platform implied by the URL, if recognized."""
    platform, _ = extract_platform_slug_from_url(url)
    return platform


def extract_slug_from_url(url: str, platform: str) -> str:
    """Extract the ATS company slug from a job URL."""
    detected_platform, slug = extract_platform_slug_from_url(url)
    if detected_platform == platform and slug:
        return slug

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    if platform == "bamboohr" and host.endswith(".bamboohr.com"):
        return slugify(host.split(".")[0])
    if path_parts:
        return slugify(path_parts[0])
    return slugify(host.split(".")[0] if host else platform)


def extract_id(url: str) -> str:
    """Robust job ID extraction from various ATS URL formats."""
    for param in ["gh_jid", "lever-via", "jobId", "id"]:
        match = re.search(rf"[?&]{param}=([a-zA-Z0-9\-_]+)", url)
        if match:
            return match.group(1)

    path = url.split("?")[0].split("#")[0].strip("/")
    parts = f"/{path}".split("/")
    if not parts:
        return ""

    if "greenhouse" in url and "jobs/" in url:
        gh_match = re.search(r"jobs/(\d+)", url)
        if gh_match:
            return gh_match.group(1)

    if "lever.co" in url:
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts[-1]

    return parts[-1] if parts else ""


def resolve_job_ref(url: str) -> ResolvedJobRef:
    platform = detect_ats_platform(url)
    if not platform:
        return ResolvedJobRef(url=url, platform=None, company_slug=None, job_id=None)

    company_slug = extract_slug_from_url(url, platform)
    job_id = extract_id(url)
    return ResolvedJobRef(
        url=url,
        platform=platform,
        company_slug=company_slug or None,
        job_id=job_id or None,
    )
