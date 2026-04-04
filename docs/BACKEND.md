# Backend — Job Radar FastAPI

Thin REST API layer over the existing Python pipeline and SQLite database. Lives in `api/`. Never imports from `src/` directly — the pipeline is treated as an opaque subprocess.

---

## Directory Structure

```
api/
├── main.py           # FastAPI app factory, router registration, static file mount
├── deps.py           # Shared FastAPI dependencies (get_store, profile paths)
├── models.py         # Pydantic request/response models
├── background.py     # Pipeline subprocess runner + in-memory polling state
└── routers/
    ├── jobs.py        # GET /api/jobs, GET /api/jobs/{id}, PATCH /api/jobs/{id}/status
    ├── stats.py       # GET /api/stats, GET /api/stats/trends
    ├── pipeline.py    # POST /api/pipeline/run, GET /api/pipeline/status/{id}, GET /api/pipeline/active, GET /api/pipeline/providers
    ├── profile.py     # GET/PUT /api/profile/{name}/yaml|doc, GET /api/profiles
    └── companies.py   # GET/POST/DELETE /api/companies/{profile}/{platform}/{slug}
```

---

## Key Design Decisions

### Store usage
Routers always use `Store` public methods through the `get_store` FastAPI dependency. They never access `store.conn` directly — the `Store` class manages connections internally via `with self._connect() as conn:`.

```python
# Correct pattern in every router
@router.get("/jobs")
def list_jobs(profile: str = "default", store: Store = Depends(get_store)):
    rows, total = store.get_jobs_filtered(...)
```

### Static file serving
In production (`make start`), FastAPI mounts the Next.js static export at `web/out/`. The `/api/*` routes are registered first, so they take priority over the static file handler.

### Pipeline subprocess
`background.py` spawns `python -m src.main --profile {name} --source {mode}` as an async subprocess. Stdout is parsed line-by-line to track step transitions. State is held in memory (sufficient for single-user local use). The frontend polls `GET /api/pipeline/status/{run_id}` every 2 seconds.

---

## Pydantic Models (api/models.py)

| Model | Purpose |
|-------|---------|
| `JobResponse` | Single job (no description field) |
| `JobDetailResponse` | Single job with full description |
| `JobListResponse` | Paginated job list + total/page counts |
| `ScoreBreakdown` | Parsed JSON from `score_breakdown` column |
| `StatusUpdate` | PATCH body for status changes |
| `StatsOverview` | Dashboard metrics |
| `TrendsResponse` | Daily counts, top skills, company stats |
| `ProviderInfo` | Provider metadata for the UI (`name`, `display_name`, `description`, `shows_aggregator_badge`) |
| `PipelineRunRequest` | POST body (`profile`, `source`, `dry_run`) |
| `PipelineRunResponse` | `run_id` string |
| `PipelineStatusResponse` | Polling response (`status`, `step`, `step_name`, `stats`, `error`) |
| `ProfileContent` | YAML/markdown file content wrapper |
| `CompanyEntry` | Single company (platform + slug + name) |

`PipelineRunRequest.source` accepts any string that matches a registered provider name (e.g. `"hybrid"`, `"aggregator"`, `"local"`). The pipeline validates this against `PROVIDER_REGISTRY` at runtime and exits with an error if the name is unknown. To see all valid values, call `GET /api/pipeline/providers`.

---

## Store Methods (src/store.py)

Methods added to support the web API (in addition to the original CLI methods):

| Method | Returns | Purpose |
|--------|---------|---------|
| `get_jobs_filtered(...)` | `(list[dict], int)` | Dynamic WHERE + pagination for job board |
| `get_job_detail(db_id)` | `dict \| None` | Single job row including description |
| `get_stats()` | `dict` | Aggregate counts for dashboard (8 metrics + distribution) |
| `get_trends(days=30)` | `dict` | Daily counts, skill frequency, company stats |

`get_jobs_filtered()` uses a whitelist for sort column names to prevent SQL injection.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROFILES_DIR` | `profiles` | Path to profiles directory |
| `DATA_DIR` | `data` | Path to SQLite databases directory |
| `ANTHROPIC_API_KEY` | — | Required for pipeline scoring |

---

## Running the API

```bash
# Development (hot reload, with Makefile)
make dev   # starts FastAPI on :8000 + Next.js on :3000

# Development (standalone)
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Production (builds Next.js then serves everything from :8000)
make start
```

Interactive API docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json` (used by `make types`)

---

## Adding New Endpoints

1. Add Pydantic model to `api/models.py`
2. Add handler to the appropriate router in `api/routers/`
3. Register the router in `api/main.py` if creating a new file
4. Run `make types` to regenerate `web/src/lib/api/types.ts`
5. Use the new typed endpoint via `api.GET(...)` / `api.POST(...)` in the frontend
