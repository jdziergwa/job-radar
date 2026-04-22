# Architecture — Job Radar

## System Overview

Job Radar has two cooperating layers:

1. Pipeline: Python CLI that collects, hydrates, filters, scores, and persists jobs
2. Web: FastAPI API plus Next.js frontend for job review, application tracking, analytics, and profile management

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Browser (Next.js)                              │
│ Dashboard │ Job Board │ Applications │ Stats │ Companies │ Settings │ Wizard │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ REST /api/*
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                               FastAPI (api/)                                │
│ /jobs /applications /stats /pipeline /companies /profile /wizard /health    │
└───────────────────────────┬───────────────────────┬─────────────────────────┘
                            │                       │
                            ▼                       ▼
┌──────────────────────────────────┐   ┌──────────────────────────────────────┐
│ SQLite store                     │   │ Python pipeline (src/)               │
│ jobs + application_events + meta │   │ providers → hydrate → prefilter      │
│ profiles + analytics caches      │   │ → score → persist                     │
└──────────────────────────────────┘   └──────────────────────────────────────┘
```

## Core Design Principles

### Frontend speaks only HTTP

The frontend consumes typed REST endpoints generated from OpenAPI into `web/src/lib/api/types.ts`. It does not reach into Python internals or SQLite details.

### Pipeline remains a subprocess

The web layer does not convert `src/` into a long-lived application service. FastAPI launches the CLI and reads structured progress output.

### SQLite is both source of truth and projection store

The DB stores:
- fetched job records
- scoring output
- tracker timeline events
- derived tracker summary fields on jobs
- cached analytics payloads
- wizard/profile metadata

### Tracker history is timeline-first

Application tracking is modeled as a sequence of events. Job-level tracker fields are derived summaries for efficient rendering in the board, job detail, and applications list.

## Directory Structure

```text
job-radar/
├── src/
│   ├── main.py
│   ├── providers/
│   ├── description_hydration.py
│   ├── fetcher.py
│   ├── models.py
│   ├── prefilter.py
│   ├── scorer.py
│   ├── reporter.py
│   ├── store.py
│   └── company_import.py
├── api/
│   ├── main.py
│   ├── deps.py
│   ├── background.py
│   ├── models.py
│   └── routers/
│       ├── jobs.py
│       ├── applications.py
│       ├── stats.py
│       ├── pipeline.py
│       ├── profile.py
│       ├── wizard.py
│       └── companies.py
├── web/
│   └── src/
│       ├── app/
│       ├── components/
│       └── lib/
├── scripts/
│   ├── build_demo_snapshot.py
│   └── import_companies.py
├── profiles/
├── data/
├── reports/
└── docs/
```

## Main Data Flows

### 1. Pipeline execution

```text
User starts run from the UI
  → POST /api/pipeline/run
  → api/background.py launches python -m src.main ...
  → pipeline collects, hydrates, filters, scores, and persists jobs
  → frontend polls GET /api/pipeline/status/{run_id}
  → dashboard / board refresh after completion
```

### 2. Job discovery and triage

```text
User opens /jobs
  → GET /api/jobs with filters
  → store.get_jobs_filtered()
  → React renders list items and job detail
  → board-level actions update /api/jobs/{id}/status or trigger rescoring
```

### 3. Application tracking

```text
User moves a job into the tracker or imports an external application
  → PATCH /api/jobs/{id}/application-status or POST /api/applications/import*
  → tracker event history is created or updated
  → derived fields on jobs are synchronized
  → /applications reads tracker projections
  → /jobs/detail reads both job data and full timeline
```

The tracker supports:
- applied date
- first response milestone
- completed journey steps
- upcoming scheduled step
- notes
- final outcomes such as accepted, rejected, withdrawn, or ghosted

### 4. Job detail tracker editing

```text
User opens /jobs/detail?id=...
  → GET /api/jobs/{id}
  → GET /api/jobs/{id}/timeline
  → UI renders Application Journey + Notes
  → tracker edits call timeline, notes, next-stage, or status endpoints
  → updated tracker projection refreshes the detail view
```

### 5. Guided profile setup

```text
User opens onboarding or Settings → Guided Edit
  → POST /api/wizard/analyze-cv
  → POST /api/wizard/generate-profile
  → POST /api/wizard/refine-profile
  → POST /api/wizard/save-profile
  → profile files + wizard state persist under profiles/{name}/
```

## Pipeline Components

### Providers

Providers implement a shared protocol and are registered in `src/providers/__init__.py`.

Current built-ins include:
- `aggregator`
- `local`
- `remotive`
- `remoteok`
- `hackernews`
- `arbeitnow`
- `weworkremotely`
- `adzuna`
- `himalayas`
- `jobicy`

### Hydration

Sparse descriptions are hydrated after collection through ATS-aware fetchers and HTML/JSON-LD fallback strategies.

### Prefilter

Regex and keyword constraints from `search_config.yaml` eliminate most noise before any LLM call.

### Scoring

Claude-based scoring runs only for survivors. `--dry-run` skips this stage entirely.

### Store

`src/store.py` is the main persistence and query layer. It serves both:
- operational reads for the API
- projection updates for tracker state
- analytics aggregation for dashboard and applications pages

## Application Tracker Model

The tracker is built on two layers:

1. Event history:
   - completed stage events
   - scheduled upcoming events
   - response milestone events

2. Derived job summary:
   - `application_status`
   - `applied_at`
   - `notes`
   - next-stage fields

This split gives:
- an auditable timeline for edits and reordering
- fast list rendering on `/jobs` and `/applications`
- simpler demo snapshot exports because the job payload already carries tracker summaries

## Demo Architecture

The hosted demo is static, but it mirrors much of the live API shape.

Demo flow:
- `scripts/build_demo_snapshot.py` exports a snapshot from `data/demo.db`
- `web/public/demo-data/` stores the baked payloads
- `web/src/lib/api/demo-fetch.ts` emulates selected API routes in the browser

Current demo behavior includes:
- board and job-detail payloads
- applications list and tracker stats
- job timeline responses
- rebased “today” counters and dates so demo data feels current

## Operational Notes

1. Provider drift is expected. The system tolerates partial failures and keeps scanning.
2. Tracker state is separate from board status; do not conflate `status` with `application_status`.
3. Analytics responses are cached briefly in metadata because they are derived but moderately expensive to rebuild.
4. Demo snapshot generation depends on `data/demo.db` if you want mocked tracker data to survive future rebuilds.
