# Backend — Job Radar FastAPI

FastAPI is a thin REST layer over the existing Python pipeline and SQLite store. It lives in `api/` and treats `src/` as an external subprocess-driven system rather than importing pipeline internals directly.

---

## Directory Structure

```
api/
├── main.py           # FastAPI app factory, router registration, static file mount
├── deps.py           # Shared FastAPI dependencies (store, profile paths)
├── models.py         # Pydantic request/response models
├── background.py     # Pipeline subprocess launcher + in-memory run state
└── routers/
    ├── jobs.py       # GET /api/jobs, GET /api/jobs/{id}, PATCH /api/jobs/{id}/status
    ├── stats.py      # GET /api/stats, GET /api/stats/trends
    ├── pipeline.py   # POST /api/pipeline/run, GET status/{id}, GET active, GET providers
    ├── profile.py    # GET/PUT /api/profile/{name}/yaml|doc, GET /api/profiles
    └── companies.py  # GET/POST/DELETE /api/companies/{profile}/{platform}/{slug}
```

---

## Key Design Decisions

### Store usage

Routers call `Store` only through public methods and the `get_store` dependency. They do not touch the SQLite connection directly.

### Static file serving

In production (`make start`), FastAPI serves the Next.js static export from `web/out/`. `/api/*` routes are mounted first, so API traffic is never shadowed by the frontend.

### Pipeline subprocess

`api/background.py` launches the CLI roughly as:

```bash
python -m src.main --profile <name> --json-progress --source aggregator local
```

It appends `--dry-run` when requested. Output is parsed line by line, and structured JSON progress events drive the pipeline status endpoint that the frontend polls every 2 seconds.

Current API behavior:
- the API accepts multiple provider names through `sources`
- the API exposes provider metadata dynamically from the registry
- CLI-only flags such as `--slow` are not yet exposed through `POST /api/pipeline/run`

---

## Pydantic Models (`api/models.py`)

| Model | Purpose |
|-------|---------|
| `JobResponse` | Single job summary |
| `JobDetailResponse` | Single job including full description |
| `JobListResponse` | Paginated job list + paging metadata |
| `ScoreBreakdown` | Parsed `score_breakdown` JSON |
| `StatusUpdate` | PATCH body for job status changes |
| `StatsOverview` | Dashboard metrics |
| `TrendsResponse` | Daily counts, skills, company stats |
| `ProviderInfo` | Provider metadata for the UI |
| `PipelineRunRequest` | POST body (`profile`, `sources`, `dry_run`) |
| `PipelineRunResponse` | `run_id` wrapper |
| `PipelineStatusResponse` | Polling response (`status`, `step`, `step_name`, `detail`, `duration`, `stats`, `error`) |
| `ProfileContent` | Raw `search_config.yaml` or `profile_doc.md` content |
| `CompanyEntry` | One tracked ATS company |

`PipelineRunRequest.sources` accepts any registered provider name, for example:
- `aggregator`
- `local`
- `remotive`
- `remoteok`
- `hackernews`
- `arbeitnow`
- `weworkremotely`
- `adzuna`

To discover the live set, call `GET /api/pipeline/providers`.

---

## Store Methods (`src/store.py`)

The API depends on these higher-level store methods:

| Method | Returns | Purpose |
|--------|---------|---------|
| `get_jobs_filtered(...)` | `(list[dict], int)` | Dynamic filters + pagination for the job board |
| `get_job_detail(db_id)` | `dict \| None` | One job row including description |
| `get_stats()` | `dict` | Dashboard totals and distributions |
| `get_trends(days=30)` | `dict` | Daily counts, skill frequency, company stats |

`get_jobs_filtered()` uses a sort-column allowlist to avoid SQL injection.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROFILES_DIR` | `profiles` | Profiles directory |
| `DATA_DIR` | `data` | SQLite database directory |
| `ANTHROPIC_API_KEY` | — | Required for scoring runs |
| `ADZUNA_APP_ID` | — | Required only for the Adzuna provider |
| `ADZUNA_APP_KEY` | — | Required only for the Adzuna provider |

---

## Running the API

```bash
# Development
make dev

# Standalone FastAPI
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Production
make start
```

Useful companion commands:
- `make test` to run the Python test suite
- `make types` to regenerate `web/src/lib/api/types.ts`

Interactive API docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## Adding New Endpoints

1. Add or update a Pydantic model in `api/models.py`.
2. Implement the handler in the appropriate router under `api/routers/`.
3. Register the router in `api/main.py` if needed.
4. Run `make types` to refresh frontend API types.
5. Consume the endpoint from the frontend through the typed API client.
