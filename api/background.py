import asyncio
import json
import uuid
import sys
from typing import TypedDict, Literal, Optional


class RunState(TypedDict):
    status: Literal["running", "done", "error", "cancelled"]
    step: int
    step_name: str
    detail: Optional[str]
    duration: Optional[float]
    stats: Optional[dict]
    skipped_steps: list[int]
    error: Optional[str]


# In-memory state — sufficient for single-user local use
_runs: dict[str, RunState] = {}
_active: dict[str, str] = {}  # profile -> run_id
_processes: dict[str, asyncio.subprocess.Process] = {}  # run_id -> proc
_cancelled: set[str] = set()  # track runs that were explicitly cancelled

# Auto-expire timeout
RUN_TIMEOUT = 300  # seconds


async def launch_pipeline(
    profile: str,
    source: str = "hybrid",
    dry_run: bool = False,
    rescore_all: bool = False,
    job_id: Optional[int] = None,
) -> str:
    """Spawn pipeline subprocess and return run_id."""
    if profile in _active:
        existing_id = _active[profile]
        if _runs.get(existing_id, {}).get("status") == "running":
            raise RuntimeError(f"Pipeline already running for profile '{profile}'")

    run_id = str(uuid.uuid4())
    _runs[run_id] = {
        "status": "running",
        "step": 1,
        "step_name": "Starting",
        "detail": None,
        "duration": 0.0,
        "stats": None,
        "skipped_steps": [],
        "error": None,
    }
    _active[profile] = run_id

    args = [sys.executable, "-m", "src.main", "--profile", profile, "--json-progress"]
    
    if rescore_all:
        args.append("--rescore")
    elif job_id:
        args += ["--job-id", str(job_id), "--rescore"]
    else:
        # Standard run
        if source != "hybrid":
            args += ["--source", source]
        else:
            args += ["--source", "hybrid"]
            
    if dry_run:
        args.append("--dry-run")

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    _processes[run_id] = proc

    asyncio.create_task(_monitor(run_id, profile, proc))
    return run_id


async def _monitor(run_id: str, profile: str, proc: asyncio.subprocess.Process):
    """Read stdout line by line to update step state."""
    try:
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").strip()
            if not line:
                continue

            # Try to parse structured JSON progress
            try:
                data = json.loads(line)
                if "progress" in data:
                    prog = data["progress"]
                    _runs[run_id]["step"] = prog.get("step", _runs[run_id]["step"])
                    _runs[run_id]["step_name"] = prog.get("name", _runs[run_id]["step_name"])
                    _runs[run_id]["detail"] = prog.get("detail", _runs[run_id]["detail"])
                    _runs[run_id]["duration"] = prog.get("duration", _runs[run_id]["duration"])
                    if _runs[run_id]["step_name"] == "Skipped":
                        step = _runs[run_id]["step"]
                        if step not in _runs[run_id]["skipped_steps"]:
                            _runs[run_id]["skipped_steps"].append(step)
                    if "stats" in prog:
                        _runs[run_id]["stats"] = prog["stats"]
                    continue
            except json.JSONDecodeError:
                pass

            # Fallback: detect steps from log lines
            lower = line.lower()
            if "collecting" in lower or "fetching" in lower:
                _runs[run_id].update(step=1, step_name="Collecting")
            elif "new job" in lower or "dedup" in lower:
                _runs[run_id].update(step=2, step_name="Deduplicating")
            elif "candidate" in lower or "pre-filter" in lower:
                _runs[run_id].update(step=3, step_name="Pre-filtering")
            elif "scoring" in lower:
                _runs[run_id].update(step=4, step_name="Scoring")

        await proc.wait()

        if run_id in _cancelled:
            _runs[run_id].update(
                status="cancelled",
                step_name="Cancelled",
                detail="Pipeline was stopped by user",
            )
            _cancelled.remove(run_id)
        elif proc.returncode == 0:
            _runs[run_id].update(status="done", step=5, step_name="Done")
            if not _runs[run_id]["stats"]:
                _runs[run_id]["stats"] = {"new_jobs": 0, "candidates": 0, "scored": 0}
        else:
            _runs[run_id].update(
                status="error",
                error=f"Pipeline exited with code {proc.returncode}",
            )
    except Exception as e:
        _runs[run_id].update(status="error", error=str(e))
    finally:
        _active.pop(profile, None)
        _processes.pop(run_id, None)


def get_status(run_id: str) -> RunState | None:
    return _runs.get(run_id)


def get_active(profile: str) -> str | None:
    return _active.get(profile)


async def cancel_pipeline(run_id: str) -> bool:
    """Send SIGTERM to the pipeline subprocess."""
    proc = _processes.get(run_id)
    if proc and proc.returncode is None:
        _cancelled.add(run_id)
        proc.terminate()
        return True
    return False
