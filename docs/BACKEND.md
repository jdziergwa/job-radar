# Backend — Job Radar FastAPI

FastAPI is the REST layer over the SQLite-backed store and the existing Python job pipeline. It lives in `api/` and treats the collector/scoring pipeline in `src/` as a subprocess-driven runtime rather than an imported service layer.

## Directory Structure

```text
api/
├── main.py           # FastAPI app setup, router registration, static export mount
├── deps.py           # Shared dependencies (store, profile paths)
├── models.py         # Pydantic request/response models
├── background.py     # Pipeline subprocess launcher + in-memory run state
└── routers/
    ├── jobs.py         # Job board list/detail/status/rescore endpoints
    ├── applications.py # Application tracker, timeline, notes, imports
    ├── stats.py        # Dashboard, trends, dismissed, market, insights
    ├── pipeline.py     # Run/cancel/status/provider endpoints
    ├── profile.py      # Raw profile file editing endpoints
    ├── wizard.py       # Guided onboarding / guided edit flow
    └── companies.py    # Curated ATS company management
```

## Router Responsibilities

### `jobs.py`

Board-oriented job discovery endpoints:
- list jobs with filtering and pagination
- fetch a single job detail
- update board-level status (`new`, `scored`, `dismissed`)
- delete manually imported jobs
- trigger rescoring for one job or all jobs

### `applications.py`

Application tracker endpoints:
- `/api/applications` and `/api/applications/stats`
- tracker state transitions through `/application-status`
- application date, response date, notes, and next-stage updates
- full timeline CRUD
- URL import and manual import flows

This router is the main bridge between job discovery and post-application workflow.

### `stats.py`

Read-only analytics endpoints:
- dashboard counters
- trends and chart payloads
- dismissal reason breakdown
- market intelligence payload
- optional LLM-generated insights report with caching

### `pipeline.py`

Subprocess control plane for collection and scoring:
- provider metadata
- run launch
- run status polling
- cancellation
- aggregator freshness

### `profile.py`

Raw file CRUD for:
- `search_config.yaml`
- `profile_doc.md`
- `scoring_philosophy.md`

### `wizard.py`

Guided onboarding and guided edit flow:
- CV analysis
- profile generation
- iterative refinement
- persisted wizard state
- template loading

### `companies.py`

Direct ATS company watchlist CRUD for `companies.yaml`.

## Key Models

Tracker-related models added in `api/models.py`:
- `ApplicationStatusUpdate`
- `ApplicationEventResponse`
- `TimelineEventDateUpdate`
- `TimelineEventCreate`
- `TimelineResponse`
- `ApplicationJobResponse`
- `ApplicationListResponse`
- `ApplicationStatsResponse`
- `ImportJobRequest`
- `ManualImportRequest`
- `ImportJobResponse`
- `NextStageUpdate`
- `AppliedAtUpdate`
- `ResponseDateUpdate`
- `NotesUpdate`

Important model split:
- `StatusUpdate` is for board-level job state only
- `ApplicationStatusUpdate` is for tracker progression and outcomes

`JobResponse` and `JobDetailResponse` now include derived tracker fields:
- `application_status`
- `applied_at`
- `notes`
- `next_stage_label`
- `next_stage_date`
- `next_stage_canonical_phase`
- `next_stage_note`

## Store Contract

The API depends on higher-level `Store` methods rather than touching SQLite directly from routers.

Board and analytics methods:
- `get_jobs_filtered(...)`
- `get_job_detail(job_id)`
- `update_status(job_id, status)`
- `delete_job(job_id)`
- `get_stats()`
- `get_trends(days=...)`
- `get_dismissal_stats()`
- `get_market_intelligence(days=...)`
- `get_jobs_for_rescore()`

Tracker methods:
- `get_applications_filtered(...)`
- `get_application_stats()`
- `update_application_status(...)`
- `update_applied_at(...)`
- `upsert_response_milestone(...)`
- `update_notes(...)`
- `update_next_stage(...)`
- `get_application_timeline(job_id)`
- `add_application_event(...)`
- `update_application_event(...)`
- `delete_application_event(...)`
- `remove_from_tracker(job_id)`
- `get_job_by_identity(...)`

The tracker data model is projection-based:
- `application_events` is the canonical timeline/history
- job-level tracker fields on `jobs` are derived summary fields used by list and detail UIs
- timeline mutations re-sync those derived job fields

## Pipeline Integration

`api/background.py` launches the CLI instead of importing pipeline code directly:

```bash
python -m src.main --profile <name> --json-progress --source aggregator local
```

Current behavior:
- supports multiple provider names
- supports `dry_run`
- supports single-job and bulk rescore launch modes
- parses structured progress events for the polling API
- does not expose every CLI-only runtime flag in the web API

## Analytics Caching

`stats.py` and `applications.py` cache derived payloads in store metadata.

Current cache behavior:
- short TTL caches avoid rebuilding heavy aggregates on every page load
- cache fingerprints include data-changing markers such as pipeline runs and status-change timestamps
- cached payloads are safe to rebuild because all analytics derive from persisted DB state

## Demo Support

The backend serves the same OpenAPI contract in normal mode, while the static demo uses frontend-side emulation for selected endpoints.

Current demo behavior:
- `scripts/build_demo_snapshot.py` exports `jobs.json`, job details, stats payloads, companies, wizard state, and profile files from `data/demo.db`
- the snapshot now includes tracker state because `JobResponse` exports tracker fields
- demo-specific application list, tracker stats, and timeline responses are implemented in `web/src/lib/api/demo-fetch.ts`
- demo “today” counters are rebased relative to the latest dataset timestamp rather than raw wall-clock build time

## Running

```bash
# Development
make dev

# Standalone API
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Production-style single server
make start
```

Useful companions:
- `make test`
- `make test-cov`
- `make types`

Interactive docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Adding or Changing Endpoints

1. Add or update models in `api/models.py`.
2. Implement the handler in the appropriate router.
3. Register the router in `api/main.py` if it is new.
4. Update store methods or pipeline integration as needed.
5. Run `make types`.
6. Update the frontend API usage and docs.
