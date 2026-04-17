from __future__ import annotations

import hashlib
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_store
from api.models import (
    ApplicationJobResponse,
    ApplicationListResponse,
    ApplicationStatsResponse,
    ApplicationStatusUpdate,
    ImportJobRequest,
    ImportJobResponse,
    JobResponse,
    ManualImportRequest,
    NextStepUpdate,
    NotesUpdate,
    TimelineResponse,
)
from src.fetcher import detect_ats_platform, extract_id, extract_slug_from_url, fetch_job_from_url
from src.providers.utils import slugify

router = APIRouter()

ALLOWED_APPLICATION_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"applied"},
    "applied": {"screening", "interviewing", "rejected_by_company", "rejected_by_user", "ghosted"},
    "screening": {"interviewing", "rejected_by_company", "rejected_by_user", "ghosted"},
    "interviewing": {"offer", "rejected_by_company", "rejected_by_user", "ghosted"},
    "offer": {"accepted", "rejected_by_user"},
    "accepted": {"rejected_by_user"},
    "rejected_by_company": {"applied"},
    "rejected_by_user": {"applied"},
    "ghosted": {"screening", "interviewing"},
}


def _external_company_slug(url: str, fallback_name: str | None = None) -> str:
    if fallback_name:
        return slugify(fallback_name)

    host = urlparse(url).netloc.lower().split(":")[0]
    parts = [
        part
        for part in host.split(".")
        if part and part not in {"www", "jobs", "careers", "boards"}
    ]
    if len(parts) >= 2:
        return slugify(parts[-2])
    if parts:
        return slugify(parts[0])
    return "external"


def _external_job_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _resolve_import_identity(url: str, fallback_name: str | None = None) -> tuple[str, str, str]:
    platform = detect_ats_platform(url)
    if platform:
        company_slug = extract_slug_from_url(url, platform)
        job_id = extract_id(url)
        if company_slug and job_id:
            return platform, company_slug, job_id
    return "external", _external_company_slug(url, fallback_name), _external_job_id(url)


def _existing_import_response(existing: dict, fetched: bool) -> ImportJobResponse:
    return ImportJobResponse(
        job_id=existing["id"],
        fetched=fetched,
        needs_manual_entry=False,
        already_tracked=True,
        job=JobResponse.from_row(existing),
    )


@router.get("/applications", response_model=ApplicationListResponse)
def list_applications(
    profile: str = Query("default"),
    status: str | None = Query(None),
    search: str | None = Query(None),
    sort: str = Query("next_step_date"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    store = get_store(profile)
    status_list = status.split(",") if status else None
    rows, total = store.get_applications_filtered(
        application_statuses=status_list,
        search=search,
        sort=sort,
        order=order,
        page=page,
        per_page=per_page,
    )
    jobs = [ApplicationJobResponse.from_row(row) for row in rows]
    return ApplicationListResponse(
        jobs=jobs,
        total=total,
        page=page,
        pages=max(1, -(-total // per_page)),
        per_page=per_page,
    )


@router.get("/applications/stats", response_model=ApplicationStatsResponse)
def get_application_stats(profile: str = Query("default")):
    store = get_store(profile)
    return ApplicationStatsResponse(**store.get_application_stats())


@router.patch("/jobs/{job_id}/application-status", response_model=JobResponse)
def update_application_status(
    job_id: int,
    body: ApplicationStatusUpdate,
    profile: str = Query("default"),
):
    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")

    current_status = existing.get("application_status")
    next_status = body.application_status
    allowed = ALLOWED_APPLICATION_TRANSITIONS.get(current_status, set())
    if current_status != next_status and next_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid application status transition: {current_status!r} -> {next_status!r}",
        )

    if not store.update_application_status(job_id, next_status, body.note):
        raise HTTPException(status_code=404, detail="Job not found")

    updated = store.get_job_detail(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_row(updated)


@router.delete("/jobs/{job_id}/application-status", response_model=JobResponse)
def delete_application_status(job_id: int, profile: str = Query("default")):
    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")

    if not store.remove_from_tracker(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    updated = store.get_job_detail(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_row(updated)


@router.patch("/jobs/{job_id}/notes", response_model=JobResponse)
def update_notes(job_id: int, body: NotesUpdate, profile: str = Query("default")):
    store = get_store(profile)
    if not store.update_notes(job_id, body.notes):
        raise HTTPException(status_code=404, detail="Job not found")

    updated = store.get_job_detail(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_row(updated)


@router.patch("/jobs/{job_id}/next-step", response_model=JobResponse)
def update_next_step(job_id: int, body: NextStepUpdate, profile: str = Query("default")):
    store = get_store(profile)
    if not store.update_next_step(job_id, body.next_step, body.next_step_date):
        raise HTTPException(status_code=404, detail="Job not found")

    updated = store.get_job_detail(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_row(updated)


@router.get("/jobs/{job_id}/timeline", response_model=TimelineResponse)
def get_timeline(job_id: int, profile: str = Query("default")):
    store = get_store(profile)
    if not store.get_job_detail(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return TimelineResponse(events=store.get_application_timeline(job_id))


@router.post("/applications/import", response_model=ImportJobResponse)
async def import_application(body: ImportJobRequest, profile: str = Query("default")):
    store = get_store(profile)
    ats_platform, company_slug, external_job_id = _resolve_import_identity(body.url, body.company_name)
    existing = store.get_job_by_identity(ats_platform, company_slug, external_job_id)
    if existing:
        return _existing_import_response(existing, fetched=False)

    fetched = False
    fetched_job = await fetch_job_from_url(body.url) if detect_ats_platform(body.url) else None
    if fetched_job:
        fetched = True
        ats_platform = str(fetched_job["ats_platform"])
        company_slug = str(fetched_job["company_slug"])
        external_job_id = str(fetched_job["job_id"])
        existing = store.get_job_by_identity(ats_platform, company_slug, external_job_id)
        if existing:
            return _existing_import_response(existing, fetched=True)

        created, already_tracked = store.import_job(
            ats_platform=ats_platform,
            company_slug=company_slug,
            external_job_id=external_job_id,
            company_name=body.company_name or str(fetched_job.get("company_name") or company_slug),
            title=body.title or str(fetched_job.get("title") or "Imported Job"),
            location=body.location or fetched_job.get("location"),
            url=body.url,
            description=fetched_job.get("description"),
            notes=body.notes,
            source="manual",
            initial_event_note="Imported from URL",
        )
        return ImportJobResponse(
            job_id=created["id"],
            fetched=True,
            needs_manual_entry=False,
            already_tracked=already_tracked,
            job=JobResponse.from_row(created),
        )

    if not body.company_name or not body.title:
        return ImportJobResponse(
            fetched=fetched,
            needs_manual_entry=True,
            already_tracked=False,
        )

    created, already_tracked = store.import_job(
        ats_platform=ats_platform,
        company_slug=company_slug,
        external_job_id=external_job_id,
        company_name=body.company_name,
        title=body.title,
        location=body.location,
        url=body.url,
        description=None,
        notes=body.notes,
        source="manual",
        initial_event_note="Imported from URL",
    )
    return ImportJobResponse(
        job_id=created["id"],
        fetched=False,
        needs_manual_entry=False,
        already_tracked=already_tracked,
        job=JobResponse.from_row(created),
    )


@router.post("/applications/import/manual", response_model=ImportJobResponse)
def import_manual_application(body: ManualImportRequest, profile: str = Query("default")):
    store = get_store(profile)
    company_slug = slugify(body.company_name)
    external_job_id = str(uuid.uuid4())
    url = body.url or f"manual://{company_slug}/{external_job_id}"
    created, already_tracked = store.import_job(
        ats_platform="manual",
        company_slug=company_slug,
        external_job_id=external_job_id,
        company_name=body.company_name,
        title=body.title,
        location=body.location,
        url=url,
        description=body.description,
        notes=body.notes,
        salary=body.salary,
        source="manual",
        initial_event_note="Manually added",
    )
    return ImportJobResponse(
        job_id=created["id"],
        fetched=False,
        needs_manual_entry=False,
        already_tracked=already_tracked,
        job=JobResponse.from_row(created),
    )
