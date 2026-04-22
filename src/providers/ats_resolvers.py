from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlparse

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


def _extract_json_ld_objects(html: str) -> list[Any]:
    matches = re.finditer(
        r'<script[^>]*type=["\']application\/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    objects: list[Any] = []
    for match in matches:
        raw_text = match.group(1).strip()
        if not raw_text:
            continue
        try:
            objects.append(json.loads(raw_text))
        except json.JSONDecodeError:
            continue
    return objects


def _find_job_posting_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        type_value = str(value.get("@type") or value.get("type") or "").lower()
        if "jobposting" in type_value:
            return value
        for nested in value.values():
            result = _find_job_posting_payload(nested)
            if result:
                return result
    elif isinstance(value, list):
        for item in value:
            result = _find_job_posting_payload(item)
            if result:
                return result
    return None


def _extract_bamboohr_title(job_posting: dict[str, Any], html: str, company_slug: str) -> str:
    title = job_posting.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title>(.*?)</title>",
        r"<h1[^>]*>(.*?)</h1>",
    ):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        raw = re.sub(r"<[^>]+>", " ", match.group(1))
        normalized = " ".join(raw.split()).strip()
        if not normalized:
            continue
        suffix = f" - {_humanize_slug(company_slug)}"
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
        return normalized

    return ""


def _extract_bamboohr_meta_content(html: str, property_name: str) -> str:
    patterns = (
        rf'<meta[^>]+property=["\']{re.escape(property_name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+name=["\']{re.escape(property_name)}["\'][^>]+content=["\']([^"\']+)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        content = " ".join(match.group(1).split()).strip()
        if content:
            return content
    return ""


def _extract_bamboohr_description(job_posting: dict[str, Any], html: str) -> str:
    description = job_posting.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()

    for pattern in (
        r'<section[^>]+(?:description|job-description|posting-content)[^>]*>(.*?)</section>',
        r'<div[^>]+(?:description|job-description|posting-content|job-details)[^>]*>(.*?)</div>',
        r"<article[^>]*>(.*?)</article>",
        r"<main[^>]*>(.*?)</main>",
    ):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            content = match.group(1).strip()
            if content:
                return content

    for meta_key in ("og:description", "twitter:description", "description"):
        content = _extract_bamboohr_meta_content(html, meta_key)
        if content:
            return content

    return ""


def _extract_bamboohr_location(job_posting: dict[str, Any], html: str) -> tuple[str, dict[str, object]]:
    metadata: dict[str, object] = {}
    workplace_type = job_posting.get("jobLocationType")
    if isinstance(workplace_type, str) and workplace_type.strip():
        workplace_text = workplace_type.strip()
        if "telecommute" in workplace_text.lower():
            workplace_text = "Remote"
        metadata["workplace_type"] = workplace_text

    address_fields: list[str] = []
    locations = job_posting.get("jobLocation")
    if isinstance(locations, dict):
        locations = [locations]
    if isinstance(locations, list):
        for location in locations:
            if not isinstance(location, dict):
                continue
            address = location.get("address")
            if not isinstance(address, dict):
                continue
            for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"):
                value = address.get(key)
                if isinstance(value, str) and value.strip():
                    address_fields.append(value.strip())

    deduped_address = _dedupe_text(address_fields)
    location = ", ".join(deduped_address)
    if location:
        metadata["raw_location"] = location

    if not location:
        for pattern in (
            r'(?is)<[^>]*>\s*Location\s*</[^>]*>\s*<[^>]*>\s*([^<]{2,120})\s*</[^>]*>',
            r'(?is)\bLocation\b\s*</[^>]*>\s*<[^>]*>\s*([^<]{2,120})\s*</[^>]*>',
        ):
            match = re.search(pattern, html)
            if match:
                location = " ".join(match.group(1).split()).strip()
                if location:
                    metadata["raw_location"] = location
                    break

    return location, metadata


def _map_bamboohr_location_type(location_type: Any) -> str | None:
    normalized = str(location_type or "").strip()
    if normalized == "1":
        return "Remote"
    return None


def build_bamboohr_job_from_detail_payload(
    payload: dict[str, Any],
    *,
    company_slug: str,
    company_name: str,
    job_id: str,
    fetched_at: str,
) -> RawJob | None:
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    job_opening = result.get("jobOpening")
    if not isinstance(job_opening, dict):
        return None

    title = str(job_opening.get("jobOpeningName") or "").strip()
    description = str(job_opening.get("description") or "").strip()
    posted_at = (
        str(job_opening.get("datePosted")).strip()
        if isinstance(job_opening.get("datePosted"), str) and job_opening.get("datePosted")
        else None
    )

    location_metadata: dict[str, object] = {}
    location = ""

    location_obj = job_opening.get("location")
    if isinstance(location_obj, dict):
        location_parts = _dedupe_text([
            str(location_obj.get("city") or "").strip(),
            str(location_obj.get("state") or "").strip(),
            str(location_obj.get("addressCountry") or "").strip(),
        ])
        if location_parts:
            location = ", ".join(location_parts)

    ats_location = job_opening.get("atsLocation")
    if not location and isinstance(ats_location, dict):
        location_parts = _dedupe_text([
            str(ats_location.get("city") or "").strip(),
            str(ats_location.get("state") or "").strip(),
            str(ats_location.get("country") or "").strip(),
        ])
        if location_parts:
            location = ", ".join(location_parts)

    workplace_type = _map_bamboohr_location_type(job_opening.get("locationType"))
    if workplace_type:
        location_metadata["workplace_type"] = workplace_type
        if not location:
            location = workplace_type

    if location:
        location_metadata["raw_location"] = location

    return RawJob(
        ats_platform="bamboohr",
        company_slug=company_slug,
        company_name=company_name,
        job_id=job_id,
        title=title,
        location=location,
        url=f"https://{company_slug}.bamboohr.com/careers/{quote(job_id)}",
        description=description,
        posted_at=posted_at,
        fetched_at=fetched_at,
        location_metadata=location_metadata,
    )


def build_bamboohr_job(
    html: str,
    *,
    company_slug: str,
    company_name: str,
    job_id: str,
    fetched_at: str,
) -> RawJob:
    job_posting: dict[str, Any] = {}
    for obj in _extract_json_ld_objects(html):
        result = _find_job_posting_payload(obj)
        if result:
            job_posting = result
            break

    location, location_metadata = _extract_bamboohr_location(job_posting, html)
    title = _extract_bamboohr_title(job_posting, html, company_slug)
    description = _extract_bamboohr_description(job_posting, html)
    posted_at = job_posting.get("datePosted") if isinstance(job_posting.get("datePosted"), str) else None

    return RawJob(
        ats_platform="bamboohr",
        company_slug=company_slug,
        company_name=company_name,
        job_id=job_id,
        title=title,
        location=location,
        url=f"https://{company_slug}.bamboohr.com/careers/{quote(job_id)}",
        description=description,
        posted_at=posted_at,
        fetched_at=fetched_at,
        location_metadata=location_metadata,
    )


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


def _extract_lever_html_title(job_posting: dict[str, Any], html: str, company_slug: str) -> str:
    title = job_posting.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<h2[^>]*>(.*?)</h2>",
        r"<title>(.*?)</title>",
    ):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        raw = re.sub(r"<[^>]+>", " ", match.group(1))
        normalized = " ".join(raw.split()).strip()
        if not normalized:
            continue
        prefix = f"{_humanize_slug(company_slug)} Careers - "
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
        return normalized

    return ""


def _extract_lever_html_location(job_posting: dict[str, Any], html: str) -> tuple[str, dict[str, object]]:
    metadata: dict[str, object] = {}

    category_match = re.search(
        r'class=["\'][^"\']*\blocation\b[^"\']*["\'][^>]*>(.*?)</div>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if category_match:
        raw = re.sub(r"<[^>]+>", " ", category_match.group(1))
        location = " ".join(raw.split()).strip(" /")
        if location:
            metadata["raw_location"] = location
            workplace_match = re.search(
                r'class=["\'][^"\']*\bworkplaceTypes\b[^"\']*["\'][^>]*>(.*?)</div>',
                html,
                re.IGNORECASE | re.DOTALL,
            )
            if workplace_match:
                workplace = " ".join(re.sub(r"<[^>]+>", " ", workplace_match.group(1)).split()).strip()
                if workplace:
                    metadata["workplace_type"] = workplace
            return location, metadata

    locations = job_posting.get("jobLocation")
    texts: list[str] = []
    if isinstance(locations, dict):
        locations = [locations]
    if isinstance(locations, list):
        for location in locations:
            if not isinstance(location, dict):
                continue
            address = location.get("address")
            if not isinstance(address, dict):
                continue
            for key in ("addressLocality", "addressRegion", "addressCountry"):
                value = address.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())

    deduped = _dedupe_text(texts)
    location = " / ".join(deduped)
    if location:
        metadata["raw_location"] = location
    return location, metadata


def build_lever_job_from_html(
    html: str,
    *,
    company_slug: str,
    company_name: str,
    job_id: str,
    fetched_at: str,
    default_url: str,
) -> RawJob:
    job_posting: dict[str, Any] = {}
    for obj in _extract_json_ld_objects(html):
        result = _find_job_posting_payload(obj)
        if result:
            job_posting = result
            break

    title = _extract_lever_html_title(job_posting, html, company_slug)
    description = ""
    description_value = job_posting.get("description")
    if isinstance(description_value, str) and description_value.strip():
        description = description_value.strip()
    location, location_metadata = _extract_lever_html_location(job_posting, html)
    posted_at = job_posting.get("datePosted") if isinstance(job_posting.get("datePosted"), str) else None

    return RawJob(
        ats_platform="lever",
        company_slug=company_slug,
        company_name=company_name,
        job_id=job_id,
        title=title,
        location=location,
        url=default_url,
        description=description,
        posted_at=posted_at,
        fetched_at=fetched_at,
        location_metadata=location_metadata,
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


def build_smartrecruiters_job(
    item: dict[str, Any],
    *,
    company_slug: str,
    company_name: str,
    fetched_at: str,
) -> RawJob:
    location_obj = item.get("location") or {}
    city = ""
    region = ""
    country = ""
    if isinstance(location_obj, dict):
        city = str(location_obj.get("city") or "").strip()
        region = str(location_obj.get("region") or location_obj.get("regionCode") or "").strip()
        country = str(location_obj.get("country") or location_obj.get("countryCode") or "").strip()

    location_parts = _dedupe_text([city, region, country])
    location = ", ".join(location_parts)

    title = item.get("name") or item.get("title") or ""
    description = item.get("jobAd", {}) if isinstance(item.get("jobAd"), dict) else {}
    description_text = ""
    for key in ("sections", "content", "jobDescription"):
        value = description.get(key)
        if isinstance(value, str) and value.strip():
            description_text = value
            break
    if not description_text:
        for key in ("jobAd", "description"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                description_text = value
                break

    job_id = str(item.get("id", ""))
    default_url = f"https://jobs.smartrecruiters.com/{company_slug}/{job_id}"
    return RawJob(
        ats_platform="smartrecruiters",
        company_slug=company_slug,
        company_name=company_name,
        job_id=job_id,
        title=str(title),
        location=location,
        url=str(item.get("ref") or item.get("jobLink") or item.get("applyUrl") or default_url),
        description=description_text,
        posted_at=item.get("releasedDate") if isinstance(item.get("releasedDate"), str) else None,
        fetched_at=fetched_at,
    )


def build_workday_job(
    payload: dict[str, Any],
    *,
    company_slug: str,
    company_name: str,
    job_id: str,
    fetched_at: str,
    default_url: str,
) -> RawJob | None:
    job_info = payload.get("jobPostingInfo")
    if not isinstance(job_info, dict):
        return None

    title = str(job_info.get("title") or "").strip()
    description = str(job_info.get("jobDescription") or "").strip()
    location = str(job_info.get("location") or "").strip()
    posted_at = str(job_info.get("startDate") or "").strip() or None
    remote_type = str(job_info.get("remoteType") or "").strip()

    if not location:
        requisition_location = job_info.get("jobRequisitionLocation")
        if isinstance(requisition_location, dict):
            location = str(requisition_location.get("descriptor") or "").strip()

    location_metadata: dict[str, object] = {}
    if location:
        location_metadata["raw_location"] = location
    if remote_type:
        location_metadata["workplace_type"] = remote_type

    hiring_organization = payload.get("hiringOrganization")
    if isinstance(hiring_organization, dict):
        resolved_company_name = str(hiring_organization.get("name") or "").strip()
        if resolved_company_name:
            company_name = resolved_company_name

    job_url = str(job_info.get("externalUrl") or "").strip() or default_url

    return RawJob(
        ats_platform="workday",
        company_slug=company_slug,
        company_name=company_name,
        job_id=job_id,
        title=title,
        location=location,
        url=job_url,
        description=description,
        posted_at=posted_at,
        fetched_at=fetched_at,
        location_metadata=location_metadata,
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
    ref: ResolvedJobRef | None = None,
) -> RawJob | None:
    response = await client.get(
        f"https://api.lever.co/v0/postings/{company_slug}/{job_id}",
        timeout=8,
    )
    if response.status_code == 200:
        payload = response.json()
        if isinstance(payload, dict):
            return build_lever_job(
                payload,
                company_slug=company_slug,
                company_name=_humanize_slug(company_slug) or company_slug,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )

    if ref is not None and ref.url:
        hosted_url = ref.url.split("?", 1)[0]
        hosted_response = await client.get(hosted_url, timeout=8, follow_redirects=True)
        if hosted_response.status_code == 200 and hosted_response.text.strip():
            job = build_lever_job_from_html(
                hosted_response.text,
                company_slug=company_slug,
                company_name=_humanize_slug(company_slug) or company_slug,
                job_id=job_id,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                default_url=hosted_url,
            )
            if job.title or job.description:
                return job
    return None


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


async def fetch_bamboohr_job(
    client: httpx.AsyncClient,
    *,
    company_slug: str,
    job_id: str,
) -> RawJob | None:
    company_name = _humanize_slug(company_slug) or company_slug
    fetched_at = datetime.now(timezone.utc).isoformat()
    job_path = quote(job_id)

    for url in (
        f"https://{company_slug}.bamboohr.com/careers/{job_path}/detail",
        f"https://{company_slug}.bamboohr.com/careers/{job_path}",
    ):
        response = await client.get(
            url,
            timeout=8,
            follow_redirects=True,
        )
        if response.status_code != 200:
            continue

        html = response.text
        if not isinstance(html, str) or not html.strip():
            continue

        if url.endswith("/detail"):
            try:
                payload = json.loads(html)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                job = build_bamboohr_job_from_detail_payload(
                    payload,
                    company_slug=company_slug,
                    company_name=company_name,
                    job_id=job_id,
                    fetched_at=fetched_at,
                )
                if job and (job.title or job.description):
                    return job

        job = build_bamboohr_job(
            html,
            company_slug=company_slug,
            company_name=company_name,
            job_id=job_id,
            fetched_at=fetched_at,
        )
        if job.title or job.description:
            return job

    return None


async def fetch_smartrecruiters_job(
    client: httpx.AsyncClient,
    *,
    company_slug: str,
    job_id: str,
) -> RawJob | None:
    response = await client.get(
        f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings/{job_id}",
        timeout=8,
    )
    if response.status_code != 200:
        return None
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return build_smartrecruiters_job(
        payload,
        company_slug=company_slug,
        company_name=_humanize_slug(company_slug) or company_slug,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


async def fetch_workday_job(
    client: httpx.AsyncClient,
    *,
    company_slug: str,
    job_id: str,
    ref: ResolvedJobRef | None = None,
) -> RawJob | None:
    source_url = ref.url if ref is not None else ""
    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if not host or len(path_parts) < 3:
        return None

    job_index = -1
    for index, part in enumerate(path_parts):
        if part == "job":
            job_index = index
            break

    if job_index <= 0:
        return None

    site = path_parts[job_index - 1]
    detail_path = "/".join(path_parts[job_index:])
    if not site or not detail_path:
        return None

    response = await client.get(
        f"https://{host}/wday/cxs/{company_slug}/{site}/{detail_path}",
        timeout=8,
    )
    if response.status_code != 200:
        return None

    payload = response.json()
    if not isinstance(payload, dict):
        return None

    default_url = source_url or f"https://{host}/{site}/{detail_path}"
    return build_workday_job(
        payload,
        company_slug=company_slug,
        company_name=_humanize_slug(company_slug) or company_slug,
        job_id=job_id,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        default_url=default_url,
    )


SingleJobFetcher = Callable[..., Awaitable[RawJob | None]]

SINGLE_JOB_FETCHERS: dict[str, SingleJobFetcher] = {
    "greenhouse": fetch_greenhouse_job,
    "lever": fetch_lever_job,
    "ashby": fetch_ashby_job,
    "workable": fetch_workable_job,
    "bamboohr": fetch_bamboohr_job,
    "smartrecruiters": fetch_smartrecruiters_job,
    "workday": fetch_workday_job,
}


async def fetch_supported_job(
    client: httpx.AsyncClient,
    ref: ResolvedJobRef,
) -> RawJob | None:
    if not ref.platform or not ref.company_slug or not ref.job_id:
        return None

    fetcher = SINGLE_JOB_FETCHERS.get(ref.platform)
    if fetcher is None:
        return None
    if ref.platform in {"lever", "workday"}:
        return await fetcher(client, company_slug=ref.company_slug, job_id=ref.job_id, ref=ref)
    return await fetcher(client, company_slug=ref.company_slug, job_id=ref.job_id)
