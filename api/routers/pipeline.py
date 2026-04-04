from fastapi import APIRouter, HTTPException, Query
from api.models import PipelineRunRequest, PipelineRunResponse, PipelineStatusResponse, ProviderInfo
import api.background as bg
from src.aggregator import get_aggregator_metadata
from src.providers import get_all_info
from api.deps import get_store

router = APIRouter()


@router.get("/pipeline/providers", response_model=list[ProviderInfo])
def list_providers():
    """Return all registered job providers for display in the UI."""
    return [info.__dict__ for info in get_all_info()]


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def run_pipeline(body: PipelineRunRequest):
    """
    Trigger the job collection + scoring pipeline.
    Returns a run_id immediately; client polls /pipeline/status/{run_id}.
    """
    # Check if a pipeline is already running for this profile
    active = bg.get_active(body.profile)
    if active:
        existing = bg.get_status(active)
        if existing and existing["status"] == "running":
            raise HTTPException(status_code=409, detail=f"Pipeline already running for profile '{body.profile}'")

    try:
        run_id = await bg.launch_pipeline(
            profile=body.profile,
            source=body.source,
            dry_run=body.dry_run,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return PipelineRunResponse(run_id=run_id)


@router.get("/pipeline/status/{run_id}", response_model=PipelineStatusResponse)
def get_pipeline_status(run_id: str):
    """
    Poll for pipeline progress. Frontend polls this every 2 seconds.
    """
    state = bg.get_status(run_id)
    if not state:
        return PipelineStatusResponse(
            status="not_found", step=0, step_name="Unknown",
            stats=None, error=None,
        )
    return PipelineStatusResponse(
        status=state["status"],
        step=state["step"],
        step_name=state["step_name"],
        detail=state.get("detail"),
        duration=state.get("duration"),
        stats=state.get("stats"),
        skipped_steps=state.get("skipped_steps", []),
        error=state.get("error"),
    )


@router.post("/pipeline/cancel/{run_id}")
async def cancel_pipeline(run_id: str):
    """
    Stop a running pipeline.
    """
    success = await bg.cancel_pipeline(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Active pipeline not found or already stopped")
    return {"status": "cancelling"}


@router.get("/pipeline/active")
def get_active_pipeline(profile: str = Query("default")):
    """Check if a pipeline is currently running for a profile."""
    run_id = bg.get_active(profile)
    state = bg.get_status(run_id) if run_id else None
    running = bool(state and state["status"] == "running")
    return {"running": running, "run_id": run_id if running else None}


@router.get("/pipeline/aggregator/status")
async def get_aggregator_status(profile: str = "default"):
    """
    Check if the local database is up to date with the remote aggregator.
    """
    live = await get_aggregator_metadata()
    store = get_store(profile)
    local_version = store.get_metadata("aggregator_version", "never")
    
    is_up_to_date = False
    if local_version != "never" and live["last_updated"] != "unknown":
        is_up_to_date = local_version == live["last_updated"]
        
    return {
        "live_updated_at": live["last_updated"],
        "local_updated_at": local_version,
        "is_up_to_date": is_up_to_date,
        "total_jobs": live["total_jobs"]
    }
