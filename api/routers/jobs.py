from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from api.deps import get_store
from api.models import JobListResponse, JobDetailResponse, JobResponse, StatusUpdate
from api import background as bg

router = APIRouter()


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    profile: str = Query("default"),
    status: Optional[str] = Query(None),          # comma-separated: "new,scored"
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    priority: Optional[str] = Query(None),         # high|medium|low|skip
    company: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("score"),                    # score|date|company
    order: str = Query("desc"),                    # asc|desc
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    days: Optional[int] = Query(None, ge=1),
    is_sparse: Optional[bool] = Query(None),
):
    """List jobs with filtering, sorting, and pagination."""
    store = get_store(profile)
    status_list = status.split(",") if status else None
    
    rows, total = store.get_jobs_filtered(
        status=status_list,
        min_score=min_score,
        max_score=max_score,
        priority=priority,
        company=company,
        search=search,
        sort=sort,
        order=order,
        page=page,
        per_page=per_page,
        days=days,
        is_sparse=is_sparse,
    )
    
    jobs = [JobResponse.from_row(row) for row in rows]
    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        pages=max(1, -(-total // per_page)),  # ceiling division
        per_page=per_page,
    )


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: int, profile: str = Query("default")):
    """Get a single job with full description."""
    store = get_store(profile)
    row = store.get_job_detail(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobDetailResponse.from_row(row)


@router.patch("/jobs/{job_id}/status")
def update_status(job_id: int, body: StatusUpdate, profile: str = Query("default")):
    """Update a job's status (applied, dismissed, etc)."""
    store = get_store(profile)
    if not store.update_status(job_id, body.status):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "id": job_id, "status": body.status}


@router.post("/jobs/{job_id}/rescore")
async def rescore_job(job_id: int, profile: str = Query("default")):
    """Trigger AI rescoring for a specific job."""
    try:
        run_id = await bg.launch_pipeline(
            profile=profile,
            job_id=job_id
        )
        return {"run_id": run_id}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/jobs/rescore/all")
async def rescore_all_jobs(profile: str = Query("default")):
    """Trigger AI rescoring for all previously scored jobs."""
    try:
        run_id = await bg.launch_pipeline(
            profile=profile,
            rescore_all=True
        )
        return {"run_id": run_id}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
