from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_store
from api.models import (
    AppliedAtUpdate,
    ApplicationJobResponse,
    ApplicationListResponse,
    ApplicationStatsResponse,
    ApplicationStatusUpdate,
    ApplicationEventResponse,
    ImportJobRequest,
    ImportJobResponse,
    JobResponse,
    ManualImportRequest,
    NextStageUpdate,
    NotesUpdate,
    ResponseDateUpdate,
    TimelineEventCreate,
    TimelineEventDateUpdate,
    TimelineResponse,
)
from api.routers.companies import ensure_company
from src.fetcher import fetch_job_from_url
from src.job_resolver import detect_ats_platform, resolve_job_ref
from src.providers.ats_registry import BULK_FETCH_ATS_PLATFORMS
from src.providers.utils import slugify

router = APIRouter()
APPLICATIONS_CACHE_TTL = timedelta(minutes=2)

ALLOWED_APPLICATION_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"applied"},
    "applied": {"screening", "interviewing", "rejected_by_company", "rejected_by_user", "ghosted"},
    "screening": {"applied", "interviewing", "rejected_by_company", "rejected_by_user", "ghosted"},
    "interviewing": {"screening", "offer", "rejected_by_company", "rejected_by_user", "ghosted"},
    "offer": {"interviewing", "accepted", "rejected_by_user"},
    "accepted": {"offer", "rejected_by_user"},
    "rejected_by_company": {"applied"},
    "rejected_by_user": {"applied"},
    "ghosted": {"screening", "interviewing"},
}


def _applications_cache_fingerprint(store) -> str:
    return "|".join([
        store.get_metadata("last_pipeline_run_at", "") or "",
        store.get_metadata("last_job_status_change_at", "") or "",
        datetime.utcnow().date().isoformat(),
    ])


def _get_cached_applications_payload(
    store,
    cache_key: str,
    fingerprint: str,
):
    cached_raw = store.get_metadata(cache_key)
    if not cached_raw:
        return None

    try:
        cached_data = json.loads(cached_raw)
        if not isinstance(cached_data, dict):
            return None
        cached_fingerprint = str(cached_data["fingerprint"])
        created_at = datetime.fromisoformat(str(cached_data["created_at"]))
        payload = cached_data["payload"]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None

    if cached_fingerprint != fingerprint:
        return None
    if datetime.utcnow() - created_at > APPLICATIONS_CACHE_TTL:
        return None
    return payload


def _get_or_build_applications_payload(
    store,
    cache_key: str,
    builder: Callable[[], dict],
):
    fingerprint = _applications_cache_fingerprint(store)
    cached_payload = _get_cached_applications_payload(store, cache_key, fingerprint)
    if cached_payload is not None:
        return cached_payload

    payload = builder()
    store.set_metadata(cache_key, json.dumps({
        "fingerprint": fingerprint,
        "created_at": datetime.utcnow().isoformat(),
        "payload": payload,
    }))
    return payload


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
    ref = resolve_job_ref(url)
    if ref.platform and ref.company_slug and ref.job_id:
        return ref.platform, ref.company_slug, ref.job_id
    return "external", _external_company_slug(url, fallback_name), _external_job_id(url)


def _existing_import_response(existing: dict, fetched: bool) -> ImportJobResponse:
    return ImportJobResponse(
        job_id=existing["id"],
        fetched=fetched,
        needs_manual_entry=False,
        already_tracked=True,
        job=JobResponse.from_row(existing),
    )


def _retracked_import_response(existing: dict, fetched: bool) -> ImportJobResponse:
    return ImportJobResponse(
        job_id=existing["id"],
        fetched=fetched,
        needs_manual_entry=False,
        already_tracked=False,
        job=JobResponse.from_row(existing),
    )


def _refresh_existing_job_from_fetched(store, existing: dict, fetched_job) -> dict:
    if not fetched_job:
        return existing
    refreshed = store.refresh_job_from_imported_fetch(existing["id"], fetched_job)
    return refreshed or existing


def _maybe_track_company(
    *,
    profile: str,
    should_track: bool,
    ats_platform: str,
    company_slug: str,
    company_name: str | None,
) -> None:
    if not should_track:
        return
    if ats_platform not in BULK_FETCH_ATS_PLATFORMS:
        return
    ensure_company(
        profile,
        platform=ats_platform,
        slug=company_slug,
        name=company_name or company_slug,
    )


def _normalize_iso_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def _resolve_timeline_timestamp(*, created_at: str | None, occurred_at: str | None) -> str:
    return occurred_at or created_at or ""


def _resolve_event_timestamp(*, created_at: str | None, occurred_at: str | None, scheduled_for: str | None) -> str:
    return scheduled_for or occurred_at or created_at or ""


def _normalize_stage_label(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _timeline_event_timestamp(event: dict) -> str:
    return str(event.get("scheduled_for") or event.get("occurred_at") or event.get("created_at") or "")


def _timeline_comparison_events(timeline: list[dict], *, event_type: str) -> list[dict]:
    if event_type != "stage":
        return timeline
    return [item for item in timeline if item.get("event_type") == "stage"]


def _build_application_list_payload(
    *,
    store,
    status: str | None,
    search: str | None,
    sort: str,
    order: str,
    page: int,
    per_page: int,
) -> dict:
    status_list = status.split(",") if status else None
    rows, total = store.get_applications_filtered(
        application_statuses=status_list,
        search=search,
        sort=sort,
        order=order,
        page=page,
        per_page=per_page,
    )
    jobs = [ApplicationJobResponse.from_row(row).model_dump() for row in rows]
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
        "per_page": per_page,
    }


@router.get("/applications", response_model=ApplicationListResponse)
def list_applications(
    profile: str = Query("default"),
    status: str | None = Query(None),
    search: str | None = Query(None),
    sort: str = Query("next_stage_date"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    store = get_store(profile)
    status_key = status or ""
    search_key = search or ""
    cache_key = (
        f"applications_cache_{profile}_{status_key}_{search_key}_{sort}_{order}_{page}_{per_page}"
    )
    payload = _get_or_build_applications_payload(
        store,
        cache_key=cache_key,
        builder=lambda: _build_application_list_payload(
            store=store,
            status=status,
            search=search,
            sort=sort,
            order=order,
            page=page,
            per_page=per_page,
        ),
    )
    return ApplicationListResponse(**payload)


@router.get("/applications/stats", response_model=ApplicationStatsResponse)
def get_application_stats(profile: str = Query("default")):
    store = get_store(profile)
    payload = _get_or_build_applications_payload(
        store,
        cache_key=f"applications_stats_cache_{profile}",
        builder=store.get_application_stats,
    )
    return ApplicationStatsResponse(**payload)


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

    if body.occurred_at:
        try:
            _normalize_iso_datetime(body.occurred_at)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid application status date") from None

    if not store.update_application_status(job_id, next_status, body.note, body.occurred_at):
        raise HTTPException(status_code=404, detail="Job not found")

    updated = store.get_job_detail(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_row(updated)


@router.patch("/jobs/{job_id}/applied-at", response_model=JobResponse)
def update_applied_at(job_id: int, body: AppliedAtUpdate, profile: str = Query("default")):
    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.get("application_status") is None:
        raise HTTPException(status_code=422, detail="Applied date can only be set for tracked jobs")
    if not store.update_applied_at(job_id, body.applied_at):
        raise HTTPException(status_code=404, detail="Job not found")
    updated = store.get_job_detail(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_row(updated)


@router.patch("/jobs/{job_id}/response-date", response_model=ApplicationEventResponse)
def update_response_date(job_id: int, body: ResponseDateUpdate, profile: str = Query("default")):
    if not body.response_date:
        raise HTTPException(status_code=422, detail="Response date is required")

    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.get("application_status") is None:
        raise HTTPException(status_code=422, detail="Response date can only be set for tracked jobs")

    applied_at = existing.get("applied_at")
    if applied_at and body.response_date < str(applied_at)[:10]:
        raise HTTPException(status_code=422, detail="Response date cannot be earlier than applied date")

    updated = store.upsert_response_milestone(job_id, body.response_date)
    if not updated:
        raise HTTPException(status_code=404, detail="Response event not found")
    return ApplicationEventResponse(**updated)


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


@router.patch("/jobs/{job_id}/next-stage", response_model=JobResponse)
def update_next_stage(job_id: int, body: NextStageUpdate, profile: str = Query("default")):
    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.get("application_status") is None:
        raise HTTPException(status_code=422, detail="Next stage can only be set for tracked jobs")

    should_mark_responded = bool(body.mark_responded or body.response_date)
    if should_mark_responded and not body.response_date:
        raise HTTPException(status_code=422, detail="Response date is required when marking the application as responded")
    applied_at = existing.get("applied_at")
    if body.response_date and applied_at and body.response_date < str(applied_at)[:10]:
        raise HTTPException(status_code=422, detail="Response date cannot be earlier than applied date")

    if not store.update_next_stage(
        job_id,
        body.stage_label,
        body.scheduled_for,
        canonical_phase=body.canonical_phase,
        note=body.note,
        mark_responded=should_mark_responded,
        response_date=body.response_date,
    ):
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


@router.post("/jobs/{job_id}/timeline", response_model=ApplicationEventResponse)
def create_timeline_event(
    job_id: int,
    body: TimelineEventCreate,
    profile: str = Query("default"),
):
    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")

    occurred_at = _resolve_timeline_timestamp(created_at=body.created_at, occurred_at=body.occurred_at)
    if not occurred_at:
        raise HTTPException(status_code=422, detail="Timeline event date is required")

    label = _normalize_stage_label(body.stage_label)
    if not label:
        raise HTTPException(status_code=422, detail="Stage label is required")

    try:
        _normalize_iso_datetime(occurred_at)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid timeline event date") from None

    timeline = store.get_application_timeline(job_id)
    completed_timeline = [item for item in timeline if item.get("lifecycle_state") != "scheduled"]
    if not completed_timeline and body.canonical_phase != "applied":
        raise HTTPException(status_code=422, detail="The first timeline event must be an applied stage")
    if completed_timeline and not any(item["status"] == "applied" for item in completed_timeline) and body.canonical_phase != "applied":
        raise HTTPException(status_code=422, detail="A tracked job must have an applied stage")

    created = store.add_application_event(
        job_id,
        canonical_phase=body.canonical_phase,
        stage_label=label,
        note=body.note,
        occurred_at=occurred_at,
    )
    if not created:
        raise HTTPException(status_code=404, detail="Job not found")
    return ApplicationEventResponse(**created)


@router.patch("/jobs/{job_id}/timeline/{event_id}", response_model=ApplicationEventResponse)
def update_timeline_event(
    job_id: int,
    event_id: int,
    body: TimelineEventDateUpdate,
    profile: str = Query("default"),
):
    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.get("application_status") is None:
        raise HTTPException(status_code=422, detail="Timeline can only be edited for tracked jobs")

    timeline = store.get_application_timeline(job_id)
    event = next((item for item in timeline if item["id"] == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Timeline event not found")

    if not body.model_fields_set:
        raise HTTPException(status_code=422, detail="At least one timeline event field must be provided")

    is_scheduled = event.get("lifecycle_state") == "scheduled"
    next_created_at = _resolve_event_timestamp(
        created_at=body.created_at,
        occurred_at=body.occurred_at,
        scheduled_for=body.scheduled_for,
    ) or _timeline_event_timestamp(event)
    next_phase = body.canonical_phase or str(event.get("canonical_phase") or event["status"])
    next_label = (
        _normalize_stage_label(body.stage_label)
        if "stage_label" in body.model_fields_set
        else None
    )
    if "stage_label" in body.model_fields_set and next_label is None:
        raise HTTPException(status_code=422, detail="Stage label cannot be empty")

    updated_dt = None
    if next_created_at:
        try:
            updated_dt = _normalize_iso_datetime(next_created_at)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid timeline event date") from None

    comparison_events = _timeline_comparison_events(timeline, event_type=str(event.get("event_type") or "stage"))
    event_index = next((index for index, item in enumerate(comparison_events) if item["id"] == event_id), None)
    if event_index is None:
        raise HTTPException(status_code=404, detail="Timeline event not found")

    if updated_dt is not None:
        if event_index > 0:
            previous_time = _timeline_event_timestamp(comparison_events[event_index - 1])
            if previous_time:
                prev_dt = _normalize_iso_datetime(previous_time)
                if prev_dt is not None and updated_dt < prev_dt:
                    raise HTTPException(status_code=422, detail="Event date cannot be earlier than the previous stage")

        if event_index < len(comparison_events) - 1:
            upcoming_time = _timeline_event_timestamp(comparison_events[event_index + 1])
            if upcoming_time:
                next_dt = _normalize_iso_datetime(upcoming_time)
                if next_dt is not None and updated_dt > next_dt:
                    raise HTTPException(status_code=422, detail="Event date cannot be later than the next stage")

    applied_events = [
        item
        for item in timeline
        if item.get("lifecycle_state") != "scheduled"
        and str(item.get("canonical_phase") or item["status"]) == "applied"
    ]
    current_phase = str(event.get("canonical_phase") or event["status"])
    if current_phase == "applied" and next_phase != "applied" and len(applied_events) <= 1:
        raise HTTPException(status_code=422, detail="Cannot remove the only applied stage")

    next_note = body.note if "note" in body.model_fields_set else event.get("note")
    updated = store.update_application_event(
        job_id,
        event_id,
        next_created_at,
        next_note,
        canonical_phase=next_phase,
        stage_label=next_label,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Timeline event not found")
    return ApplicationEventResponse(**updated)


@router.delete("/jobs/{job_id}/timeline/{event_id}", response_model=TimelineResponse)
def delete_timeline_event(job_id: int, event_id: int, profile: str = Query("default")):
    store = get_store(profile)
    existing = store.get_job_detail(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.get("application_status") is None:
        raise HTTPException(status_code=422, detail="Timeline can only be edited for tracked jobs")

    timeline = store.get_application_timeline(job_id)
    event = next((item for item in timeline if item["id"] == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Timeline event not found")
    completed_events = [item for item in timeline if item.get("lifecycle_state") != "scheduled"]
    if event.get("lifecycle_state") != "scheduled" and len(completed_events) <= 1:
        raise HTTPException(status_code=422, detail="Cannot delete the only timeline event")

    applied_events = [
        item
        for item in completed_events
        if item["status"] == "applied"
    ]
    if event.get("lifecycle_state") != "scheduled" and event["status"] == "applied" and len(applied_events) <= 1:
        raise HTTPException(status_code=422, detail="Cannot remove the only applied event")

    if not store.delete_application_event(job_id, event_id):
        raise HTTPException(status_code=404, detail="Timeline event not found")
    return TimelineResponse(events=store.get_application_timeline(job_id))


@router.post("/applications/import", response_model=ImportJobResponse)
async def import_application(body: ImportJobRequest, profile: str = Query("default")):
    store = get_store(profile)
    ats_platform, company_slug, external_job_id = _resolve_import_identity(body.url, body.company_name)
    existing = store.get_job_by_identity(ats_platform, company_slug, external_job_id)
    if existing:
        fetched_job = await fetch_job_from_url(body.url) if detect_ats_platform(body.url) else None
        existing = _refresh_existing_job_from_fetched(store, existing, fetched_job)
        if existing.get("application_status") is None:
            if not store.update_application_status(existing["id"], "applied", "Re-added from URL import"):
                raise HTTPException(status_code=404, detail="Job not found")
            if body.applied_at is not None:
                store.update_applied_at(existing["id"], body.applied_at)
            if body.notes:
                store.update_notes(existing["id"], body.notes)
            _maybe_track_company(
                profile=profile,
                should_track=body.track_company_in_pipeline,
                ats_platform=ats_platform,
                company_slug=company_slug,
                company_name=existing.get("company_name"),
            )
            updated = store.get_job_detail(existing["id"])
            if not updated:
                raise HTTPException(status_code=404, detail="Job not found")
            return _retracked_import_response(updated, fetched=False)
        _maybe_track_company(
            profile=profile,
            should_track=body.track_company_in_pipeline,
            ats_platform=ats_platform,
            company_slug=company_slug,
            company_name=existing.get("company_name"),
        )
        return _existing_import_response(existing, fetched=False)

    fetched = False
    fetched_job = await fetch_job_from_url(body.url) if detect_ats_platform(body.url) else None
    if fetched_job:
        fetched = True
        ats_platform = fetched_job.ats_platform
        company_slug = fetched_job.company_slug
        external_job_id = fetched_job.job_id
        existing = store.get_job_by_identity(ats_platform, company_slug, external_job_id)
        if existing:
            existing = _refresh_existing_job_from_fetched(store, existing, fetched_job)
            if existing.get("application_status") is None:
                if not store.update_application_status(existing["id"], "applied", "Re-added from URL import"):
                    raise HTTPException(status_code=404, detail="Job not found")
                if body.applied_at is not None:
                    store.update_applied_at(existing["id"], body.applied_at)
                if body.notes:
                    store.update_notes(existing["id"], body.notes)
                _maybe_track_company(
                    profile=profile,
                    should_track=body.track_company_in_pipeline,
                    ats_platform=ats_platform,
                    company_slug=company_slug,
                    company_name=existing.get("company_name") or fetched_job.company_name,
                )
                updated = store.get_job_detail(existing["id"])
                if not updated:
                    raise HTTPException(status_code=404, detail="Job not found")
                return _retracked_import_response(updated, fetched=True)
            _maybe_track_company(
                profile=profile,
                should_track=body.track_company_in_pipeline,
                ats_platform=ats_platform,
                company_slug=company_slug,
                company_name=existing.get("company_name") or fetched_job.company_name,
            )
            return _existing_import_response(existing, fetched=True)

        created, already_tracked = store.import_job(
            ats_platform=ats_platform,
            company_slug=company_slug,
            external_job_id=external_job_id,
            company_name=body.company_name or fetched_job.company_name or company_slug,
            title=body.title or fetched_job.title or "Imported Job",
            location=body.location or fetched_job.location,
            url=fetched_job.url or body.url,
            description=fetched_job.description,
            applied_at=body.applied_at,
            notes=body.notes,
            company_metadata=fetched_job.company_metadata,
            location_metadata=fetched_job.location_metadata,
            salary=fetched_job.salary,
            salary_min=fetched_job.salary_min,
            salary_max=fetched_job.salary_max,
            salary_currency=fetched_job.salary_currency,
            source="manual",
            initial_event_note="Imported from URL",
        )
        _maybe_track_company(
            profile=profile,
            should_track=body.track_company_in_pipeline,
            ats_platform=ats_platform,
            company_slug=company_slug,
            company_name=body.company_name or fetched_job.company_name or company_slug,
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
        applied_at=body.applied_at,
        notes=body.notes,
        source="manual",
        initial_event_note="Imported from URL",
    )
    _maybe_track_company(
        profile=profile,
        should_track=body.track_company_in_pipeline,
        ats_platform=ats_platform,
        company_slug=company_slug,
        company_name=body.company_name,
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
        applied_at=body.applied_at,
        notes=body.notes,
        salary=body.salary,
        source="manual",
        initial_event_note="Manually added",
    )
    if body.url:
        ref = resolve_job_ref(body.url)
        if ref.platform and ref.company_slug:
            _maybe_track_company(
                profile=profile,
                should_track=body.track_company_in_pipeline,
                ats_platform=ref.platform,
                company_slug=ref.company_slug,
                company_name=body.company_name,
            )
    return ImportJobResponse(
        job_id=created["id"],
        fetched=False,
        needs_manual_entry=False,
        already_tracked=already_tracked,
        job=JobResponse.from_row(created),
    )
