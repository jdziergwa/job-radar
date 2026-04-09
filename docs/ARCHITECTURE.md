# Architecture — Job Radar

## System Overview

Job Radar has two layers:

1. **Pipeline** — Python CLI that collects, hydrates, filters, scores, and persists jobs
2. **Web** — FastAPI REST API + Next.js frontend for browsing and managing results

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Next.js)                           │
│   Dashboard │ Job Board │ Stats │ Companies │ Settings              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  REST /api/*
┌──────────────────────────────▼──────────────────────────────────────┐
│                         FastAPI (api/)                              │
│   /api/jobs  /api/stats  /api/pipeline  /api/companies  /api/profile│
└────────┬─────────────────────┬──────────────────────────────────────┘
         │                     │
         ▼                     ▼
┌─────────────────┐   ┌────────────────────────────────────────────────┐
│  SQLite DB      │   │  Python Pipeline (src/)                        │
│  data/{name}.db │   │  Providers → Hydration → Pre-filter → Scorer   │
└─────────────────┘   └────────────────────────────────────────────────┘
```

---

## Design Principles

### 1. Backend-agnostic frontend
The Next.js frontend talks only to the REST contract generated into `web/src/lib/api/types.ts`. It does not know about Python internals or SQLite details.

### 2. API contract enforced by OpenAPI
FastAPI generates an OpenAPI spec, and `openapi-typescript` turns it into frontend types.

```bash
make types
```

### 3. Pipeline stays a subprocess
`src/` is not used as an imported application service layer by the web app. `api/background.py` launches the CLI and parses progress output.

### 4. User data stays isolated
Profile content, databases, and reports live under `profiles/`, `data/`, and `reports/`, keeping the application code publishable without personal data.

---

## Directory Structure

```
job-radar/
│
├── src/
│   ├── main.py                       # CLI entry point + orchestration
│   ├── providers/
│   │   ├── __init__.py               # JobProvider protocol, registry, provider metadata
│   │   ├── aggregator.py             # Aggregator provider
│   │   ├── local_ats.py              # Direct ATS collection (Greenhouse, Lever, Ashby, Workable)
│   │   ├── remotive.py               # Remotive provider
│   │   ├── remoteok.py               # Remote OK provider
│   │   ├── hackernews.py             # Hacker News provider
│   │   ├── arbeitnow.py              # Arbeitnow provider
│   │   ├── weworkremotely.py         # We Work Remotely provider
│   │   └── adzuna.py                 # Adzuna provider
│   ├── description_hydration.py      # Sparse/missing description hydration rules
│   ├── fetcher.py                    # Lazy description fetcher
│   ├── models.py                     # RawJob, CandidateJob, ScoredJob dataclasses
│   ├── store.py                      # SQLite persistence + query layer
│   ├── prefilter.py                  # Regex pre-filter
│   ├── scorer.py                     # Claude integration
│   ├── reporter.py                   # Terminal, markdown, Telegram output
│   └── company_import.py             # ATS company import helpers
│
├── scripts/
│   └── import_companies.py           # CLI wrapper for company import automation
│
├── api/
│   ├── main.py
│   ├── deps.py
│   ├── models.py
│   ├── background.py
│   └── routers/
│       ├── jobs.py
│       ├── stats.py
│       ├── pipeline.py
│       ├── profile.py
│       └── companies.py
│
├── web/
│   └── src/
│       ├── app/
│       ├── components/
│       └── lib/
│
├── profiles/
│   ├── example/
│   └── default/
│
├── data/
├── reports/
├── docs/
├── .env
├── .env.example
├── Makefile
└── requirements.txt
```

---

## Data Flow

### Pipeline execution
```
User triggers a run
  → POST /api/pipeline/run {profile, sources, dry_run}
  → background.py spawns: python -m src.main --profile default --source aggregator local
  → Pipeline: Collect → Deduplicate → Hydrate → Pre-filter → Score → Store results
  → Frontend polls GET /api/pipeline/status/{run_id}
  → On completion: frontend refreshes jobs and stats
```

### Job browsing
```
User opens /jobs
  → GET /api/jobs?...filters...
  → router calls store.get_jobs_filtered()
  → Returns paginated JSON
  → React renders the current slice
```

---

## Pipeline Components

### Provider system (`src/providers/__init__.py`)
Providers implement a common `JobProvider` protocol and are registered in `PROVIDER_REGISTRY`.

Current built-ins:
- `aggregator`
- `local`
- `remotive`
- `remoteok`
- `hackernews`
- `arbeitnow`
- `weworkremotely`
- `adzuna`

The web UI reads this registry via `GET /api/pipeline/providers`.

### Local ATS collection (`src/providers/local_ats.py`)
The direct ATS provider fetches from:
- **Greenhouse**: `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`
- **Lever**: `GET https://api.lever.co/v0/postings/{slug}?mode=json`
- **Ashby**: `POST https://api.ashbyhq.com/posting-api/job-board/{slug}`
- **Workable**: `GET https://apply.workable.com/api/v1/widget/{slug}`

It uses:
- platform-specific concurrency caps
- optional pacing per platform
- runtime-aware slow mode for large scans

### Description hydration (`src/description_hydration.py` + `src/fetcher.py`)
Providers are allowed to return partial text. After collection, the pipeline tries to hydrate jobs with missing or sparse descriptions through ATS-specific fetchers, JSON-LD parsing, and HTML fallback scraping. Short source text can be merged into the hydrated result instead of being replaced.

### Pre-filter (`src/prefilter.py`)
Regex-based filtering trims the candidate set before LLM scoring. Matching rules come from `search_config.yaml`.

### Scorer (`src/scorer.py`)
Claude-based fit scoring runs only after pre-filtering. `--dry-run` skips this stage entirely.

### Store (`src/store.py`)
SQLite is the system of record for fetched jobs, scoring output, and metadata such as aggregator versioning.

### Company import tooling (`src/company_import.py` + `scripts/import_companies.py`)
This tooling converts external JSON datasets into mergeable `companies.yaml` fragments so the curated direct ATS list can scale without hand-editing every entry.

---

## Operational Notes

1. **Ashby** uses a POST endpoint and may change behavior without notice.
2. **Workable** often returns sparse content, so downstream hydration matters.
3. **Greenhouse** returns HTML in `content`; the frontend can render it directly.
4. **Dead slugs and provider drift** are expected. Providers log failures and continue instead of crashing the whole run.
5. **Slow mode** exists for safer ATS scans, but it is currently a CLI/runtime capability rather than a web-exposed pipeline option.
