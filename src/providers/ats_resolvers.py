from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import httpx

from src.job_resolver import ResolvedJobRef
from src.models import RawJob
from src.providers.utils import slugify


def _humanize_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value or "").split("-") if part).strip()


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = " ".join(str(value).split()).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def _extract_ashby_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(_extract_ashby_text_values(item))
        return values
    if isinstance(value, dict):
        values: list[str] = []
        for key in ("name", "label", "text", "value", "title"):
            text = value.get(key)
            if isinstance(text, str):
                values.append(text)
        return values
    return []


def _derive_geographic_signals(location_texts: list[str], description: str) -> list[str]:
    combined = " ".join(location_texts + ([description] if description else []))
    lowered = combined.lower()
    signals: list[str] = []

    def add(signal: str) -> None:
        if signal not in signals:
            signals.append(signal)

    if "remote" in lowered:
        add("Remote role")
    if re.search(r"\b(worldwide|global|anywhere)\b", lowered):
        add("Explicitly global or worldwide remote")
    if re.search(r"\b(us|u\.s\.|usa|united states)\b(?:[-\s]+only|\s+only|\s+based|\s+residents?)", lowered):
        add("Restricted to United States")
    if re.search(r"\bnorth america\b(?:[-\s]+only|\s+only)?", lowered):
        add("Restricted to North America")
    if re.search(r"\b(europe|eu)\b(?:[-\s]+only|\s+only)?", lowered):
        add("Restricted to Europe")
    if re.search(r"\bemea\b(?:[-\s]+only|\s+only)?", lowered):
        add("Restricted to EMEA")
    if re.search(r"\b(?:timezone|time zone|hours?\s+overlap|overlap\s+hours?|utc|gmt|cet|cest|eet|eest|est|edt|cst|cdt|mst|mdt|pst|pdt|eastern time|central time|mountain time|pacific time)\b", lowered):
        add("Timezone overlap requirement mentioned")

    return signals


def extract_ashby_description(item: dict[str, Any]) -> str:
    for key in (
        "descriptionHtml",
        "descriptionPlain",
        "jobDescriptionHtml",
        "jobDescriptionPlain",
        "description",
    ):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def build_ashby_location_metadata(item: dict[str, Any], location: str, description: str) -> dict[str, object]:
    fragments = _dedupe_text(
        [location]
        + _extract_ashby_text_values(item.get("secondaryLocations"))
        + _extract_ashby_text_values(item.get("locationRestrictions"))
        + _extract_ashby_text_values(item.get("remoteLocation"))
        + _extract_ashby_text_values(item.get("remoteLocations"))
    )

    metadata: dict[str, object] = {"raw_location": location}

    workplace_type = item.get("workplaceType")
    if isinstance(workplace_type, str) and workplace_type.strip():
        metadata["workplace_type"] = workplace_type.strip()

    employment_type = item.get("employmentType")
    if isinstance(employment_type, str) and employment_type.strip():
        metadata["employment_type"] = employment_type.strip()

    if fragments:
        metadata["location_fragments"] = fragments

    derived_signals = _derive_geographic_signals(fragments, description)
    if derived_signals:
        metadata["derived_geographic_signals"] = derived_signals

    return metadata


def _extract_greenhouse_location(item: dict[str, Any]) -> str:
    location_obj = item.get("location") or {}
    if isinstance(location_obj, dict):
        name = location_obj.get("name")
        return name if isinstance(name, str) else ""
    return str(location_obj or "")


def build_greenhouse_job(
    item: dict[str, Any],
    *,
    company_slug: str,
    company_name: str,
    fetched_at: str,
) -> RawJob:
    return RawJob(
        ats_platform="greenhouse",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(item.get("id", "")),
        title=str(item.get("title", "")),
        location=_extract_greenhouse_location(item),
        url=str(item.get("absolute_url", "")),
        description=str(item.get("content", "") or ""),
        posted_at=item.get("updated_at") if isinstance(item.get("updated_at"), str) else None,
        fetched_at=fetched_at,
    )


def _build_lever_description(item: dict[str, Any]) -> str:
    parts: list[str] = []
    intro = item.get("description") or item.get("descriptionPlain") or ""
    if isinstance(intro, str) and intro:
        parts.append(intro)

    lists = item.get("lists")
    if isinstance(lists, list):
        for section in lists:
            if not isinstance(section, dict):
                continue
            header = section.get("text")
            content = section.get("content")
            if content:
                if isinstance(header, str) and header:
                    parts.append(f"<h3>{header}</h3>")
                if isinstance(content, list):
                    parts.append("<ul>" + "".join(f"<li>{entry}</li>" for entry in content) + "</ul>")
                elif isinstance(content, str):
                    parts.append(content)

    additional = item.get("additional") or item.get("additionalPlain")
    if isinstance(additional, str) and additional:
        parts.append("<h3>Additional Information</h3>")
        parts.append(additional)

    return "\n\n".join(parts) if parts else ""


def build_lever_job(
    item: dict[str, Any],
    *,
    company_slug: str,
    company_name: str,
    fetched_at: str,
) -> RawJob:
    categories = item.get("categories", {}) or {}
    location = categories.get("location", "") if isinstance(categories, dict) else ""
    title = item.get("text") or item.get("title") or ""
    return RawJob(
        ats_platform="lever",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(item.get("id", "")),
        title=str(title),
        location=str(location or ""),
        url=str(item.get("hostedUrl", "") or item.get("applyUrl", "")),
        description=_build_lever_description(item),
        posted_at=None,
        fetched_at=fetched_at,
    )


def _build_workable_description(item: dict[str, Any]) -> str:
    parts = [
        part
        for part in (
            item.get("description"),
            item.get("requirements"),
            item.get("benefits"),
        )
        if isinstance(part, str) and part
    ]
    return "\n".join(parts)


def build_workable_job(
    item: dict[str, Any],
    *,
    company_slug: str,
    company_name: str,
    fetched_at: str,
) -> RawJob:
    city = item.get("city", "") or ""
    country = item.get("country", "") or ""
    location = f"{city}, {country}".strip(", ") if city or country else ""
    job_url = item.get("url", "") or f"https://apply.workable.com/{company_slug}/j/{item.get('shortcode', item.get('id', ''))}/"
    return RawJob(
        ats_platform="workable",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(item.get("id", item.get("shortcode", ""))),
        title=str(item.get("title", "")),
        location=location,
        url=str(job_url),
        description=_build_workable_description(item),
        posted_at=None,
        fetched_at=fetched_at,
    )


def _extract_ashby_company_name(payload: dict[str, Any], company_slug: str) -> str:
    for key in ("companyName", "name", "organizationName", "organization_name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _humanize_slug(company_slug) or company_slug


def _extract_ashby_salary(item: dict[str, Any]) -> str | None:
    for key in (
        "compensationTierSummary",
        "compensationSummary",
        "salary",
        "salarySummary",
        "compensation",
    ):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested_key in ("summary", "displayText", "text", "shortSummary", "longSummary"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return None


def build_ashby_job(
    item: dict[str, Any],
    *,
    company_slug: str,
    company_name: str,
    fetched_at: str,
) -> RawJob:
    location = item.get("location", "") or ""
    if isinstance(location, dict):
        location = location.get("name", "")
    location = str(location or "")
    description = extract_ashby_description(item)
    return RawJob(
        ats_platform="ashby",
        company_slug=company_slug,
        company_name=company_name,
        job_id=str(item.get("id", "")),
        title=str(item.get("title", "")),
        location=location,
        url=f"https://jobs.ashbyhq.com/{company_slug}/{item.get('id', '')}",
        description=description,
        posted_at=item.get("publishedDate") if isinstance(item.get("publishedDate"), str) else None,
        fetched_at=fetched_at,
        location_metadata=build_ashby_location_metadata(item, location, description),
        salary=_extract_ashby_salary(item),
    )


async def fetch_greenhouse_job(
    client: httpx.AsyncClient,
    *,
    company_slug: str,
    job_id: str,
) -> RawJob | None:
    slugs_to_try = [company_slug]
    if "pro" not in company_slug:
        slugs_to_try.append(f"{company_slug}pro")
    if "-" in company_slug:
        slugs_to_try.append(company_slug.replace("-", ""))
    else:
        slugs_to_try.append("-".join(re.findall(r"[a-z]+", company_slug)))
    slugs_to_try = list(dict.fromkeys(slugs_to_try))

    for slug in slugs_to_try:
        response = await client.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}",
            timeout=8,
        )
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, dict):
                return build_greenhouse_job(
                    payload,
                    company_slug=company_slug,
                    company_name=_humanize_slug(company_slug) or company_slug,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
        elif response.status_code != 404:
            break
    return None


async def fetch_lever_job(
    client: httpx.AsyncClient,
    *,
    company_slug: str,
    job_id: str,
) -> RawJob | None:
    response = await client.get(
        f"https://api.lever.co/v0/postings/{company_slug}/{job_id}",
        timeout=8,
    )
    if response.status_code != 200:
        return None
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return build_lever_job(
        payload,
        company_slug=company_slug,
        company_name=_humanize_slug(company_slug) or company_slug,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


async def fetch_ashby_job(
    client: httpx.AsyncClient,
    *,
    company_slug: str,
    job_id: str,
) -> RawJob | None:
    response = await client.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}",
        params={"includeCompensation": "true"},
        timeout=8,
    )
    if response.status_code != 200:
        return None

    payload = response.json()
    if not isinstance(payload, dict):
        return None
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return None
    item = next((entry for entry in jobs if str(entry.get("id", "")) == job_id), None)
    if not isinstance(item, dict):
        return None
    return build_ashby_job(
        item,
        company_slug=company_slug,
        company_name=_extract_ashby_company_name(payload, company_slug),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


async def fetch_workable_job(
    client: httpx.AsyncClient,
    *,
    company_slug: str,
    job_id: str,
) -> RawJob | None:
    response = await client.get(
        f"https://apply.workable.com/api/v3/accounts/{company_slug}/jobs/{job_id}",
        timeout=8,
    )
    if response.status_code != 200:
        return None
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return build_workable_job(
        payload,
        company_slug=company_slug,
        company_name=_humanize_slug(company_slug) or company_slug,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


async def fetch_supported_job(
    client: httpx.AsyncClient,
    ref: ResolvedJobRef,
) -> RawJob | None:
    if not ref.platform or not ref.company_slug or not ref.job_id:
        return None

    if ref.platform == "greenhouse":
        return await fetch_greenhouse_job(client, company_slug=ref.company_slug, job_id=ref.job_id)
    if ref.platform == "lever":
        return await fetch_lever_job(client, company_slug=ref.company_slug, job_id=ref.job_id)
    if ref.platform == "ashby":
        return await fetch_ashby_job(client, company_slug=ref.company_slug, job_id=ref.job_id)
    if ref.platform == "workable":
        return await fetch_workable_job(client, company_slug=ref.company_slug, job_id=ref.job_id)
    return None
