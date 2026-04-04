# Architecture — Job Radar

## System Overview

Job Radar has two layers:

1. **Pipeline** — Python CLI that collects, filters, scores and persists jobs
2. **Web** — FastAPI REST API + Next.js 16 frontend for browsing and managing results

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Next.js 16)                        │
│   Dashboard │ Job Board │ Stats │ Companies │ Settings              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  REST /api/*
┌──────────────────────────────▼──────────────────────────────────────┐
│                        FastAPI  (api/)                               │
│   /api/jobs  /api/stats  /api/pipeline  /api/companies  /api/profile │
└────────┬─────────────────────┬───────────────────────────────────────┘
         │                     │
         ▼                     ▼
┌─────────────────┐   ┌────────────────────────────────────────────────┐
│  SQLite DB      │   │  Python Pipeline  (src/)                       │
│  data/{name}.db │   │  Collector → Store → Pre-filter → Scorer       │
│                 │   │  Triggered via subprocess from /api/pipeline    │
└─────────────────┘   └────────────────────────────────────────────────┘
```

---

## Design Principles

### 1. Backend-agnostic frontend
The Next.js frontend talks only to a REST API contract defined in `web/src/lib/api/types.ts`. It has no knowledge of Python, SQLite, or FastAPI. When the backend is replaced with TypeScript, zero frontend code changes — only the server implementation changes.

### 2. API contract enforced by openapi-typescript
FastAPI auto-generates an OpenAPI spec. `openapi-typescript` converts it to `types.ts`. If a Pydantic model changes, TypeScript compilation breaks on the frontend.

```bash
make types  # regenerate types.ts from live FastAPI spec
```

### 3. Pipeline stays unchanged
`src/` is never imported by the web layer. `api/background.py` spawns the pipeline as a subprocess. The web layer only reads from the database and triggers runs.

### 4. User data fully isolated
All user-specific data lives in `profiles/`, `data/`, `reports/`. These are gitignored. The entire `src/`, `api/`, `web/` tree is publishable to GitHub with no personal information.

---

## Directory Structure

```
job-radar/
│
├── src/                              # Python pipeline — never modified by web layer
│   ├── main.py                       # CLI entry point
│   ├── providers.py                  # JobProvider protocol, registry, built-in providers
│   ├── collector.py                  # ATS API fetchers (Greenhouse, Lever, Ashby, Workable)
│   ├── aggregator.py                 # Remote job aggregator source
│   ├── fetcher.py                    # Lazy description fetcher
│   ├── models.py                     # RawJob, CandidateJob, ScoredJob dataclasses
│   ├── store.py                      # SQLite persistence + query layer
│   ├── prefilter.py                  # Regex keyword filter
│   ├── scorer.py                     # Claude API integration
│   └── reporter.py                   # Terminal + markdown + Telegram output
│
├── api/                              # FastAPI server — thin layer over SQLite
│   ├── main.py                       # App factory, router registration, static file mount
│   ├── deps.py                       # Shared dependencies (get_store, profile paths)
│   ├── models.py                     # Pydantic request/response models
│   ├── background.py                 # Subprocess runner + in-memory polling state
│   └── routers/
│       ├── jobs.py                   # GET /api/jobs, GET /api/jobs/{id}, PATCH status
│       ├── stats.py                  # GET /api/stats, GET /api/stats/trends
│       ├── pipeline.py               # POST /api/pipeline/run, GET status/{id}, GET active
│       ├── profile.py                # GET/PUT /api/profile/{name}/yaml|doc, GET /api/profiles
│       └── companies.py              # GET/POST/DELETE /api/companies/{profile}/{platform}/{slug}
│
├── web/                              # Next.js 16 App Router (static export)
│   └── src/
│       ├── app/                      # Pages
│       │   ├── page.tsx              # Dashboard
│       │   ├── jobs/page.tsx         # Job board with filters and pagination
│       │   ├── jobs/[id]/page.tsx    # Job detail, score breakdown, status management
│       │   ├── stats/page.tsx        # Activity, skills, and distribution charts
│       │   ├── companies/page.tsx    # Company list management (tabbed by ATS)
│       │   └── settings/page.tsx     # Profile YAML and markdown doc editor
│       ├── components/
│       │   ├── ui/                   # shadcn/ui primitives
│       │   ├── layout/               # Sidebar (collapsible), ThemeToggle
│       │   ├── jobs/                 # JobListItem, FilterPanel
│       │   ├── score/                # ScoreRing (SVG animated), ScoreBar, PriorityBadge
│       │   ├── stats/                # ActivityChart, SkillsChart, DistributionChart
│       │   ├── dashboard/            # HighPriorityTable, QuickActions
│       │   └── pipeline/             # PipelineTrigger (dialog with stepper + terminal view)
│       └── lib/
│           ├── api/
│           │   ├── types.ts          # AUTO-GENERATED — do not edit manually
│           │   └── client.ts         # openapi-fetch instance (single backend switchover point)
│           └── utils/
│               ├── format.ts         # timeAgo, formatDate helpers
│               └── score.ts          # Score colour/label helpers
│
├── profiles/
│   ├── example/                      # Committed template for new users
│   └── default/                      # Gitignored — user's actual profile
│
├── data/                             # Gitignored — per-profile SQLite databases
├── reports/                          # Gitignored — markdown reports from CLI runs
├── docs/                             # Reference documentation
├── .env                              # Gitignored — API keys
├── .env.example                      # Committed — key names reference
├── Makefile
└── requirements.txt
```

---

## Data Flow

### Pipeline execution (triggered from web)
```
User clicks "Run Pipeline" in browser
  → POST /api/pipeline/run {profile, source, dry_run}
  → background.py spawns: python -m src.main --profile default --source hybrid
  → Pipeline: Collect → Deduplicate → Pre-filter → Score → Store results
  → Frontend polls GET /api/pipeline/status/{run_id} every 2 seconds
  → On done: frontend refreshes job list
```

### Job browsing
```
User opens /jobs
  → GET /api/jobs?status=scored&min_score=60&sort=score&limit=20
  → jobs.py calls store.get_jobs_filtered()
  → Returns paginated JSON with parsed score_breakdown
  → React renders JobListItem stack
```

### Score breakdown
The `score_breakdown` column stores JSON that FastAPI parses into a structured Pydantic model:
```json
{
  "dimensions": {
    "tech_stack_match": 90,
    "seniority_match": 85,
    "remote_location_fit": 80,
    "growth_potential": 75
  },
  "key_matches": ["Playwright", "CI/CD", "Python"],
  "red_flags": ["Requires on-site"],
  "apply_priority": "high"
}
```

---

## SQLite Schema

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ats_platform TEXT NOT NULL,          -- greenhouse | lever | ashby | workable
    company_slug TEXT NOT NULL,
    job_id TEXT NOT NULL,                -- ATS-specific ID
    company_name TEXT,
    title TEXT NOT NULL,
    location TEXT,
    url TEXT NOT NULL,
    description TEXT,
    posted_at TEXT,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT,
    fit_score INTEGER,                   -- 0-100, null if unscored
    score_reasoning TEXT,
    score_breakdown TEXT,                -- JSON (see above)
    scored_at TEXT,
    status TEXT DEFAULT 'new',          -- new | scored | applied | dismissed | closed
    UNIQUE(ats_platform, company_slug, job_id)
);

CREATE INDEX idx_first_seen ON jobs(first_seen_at);
CREATE INDEX idx_status ON jobs(status);
CREATE INDEX idx_score ON jobs(fit_score);
CREATE INDEX idx_last_seen ON jobs(last_seen_at);
```

---

## API Layer Design

All endpoints prefixed `/api/`. In development, Next.js proxies `/api/*` to FastAPI at `:8000`. In production, FastAPI serves both the API and the static Next.js build from `web/out/`.

- `NEXT_PUBLIC_API_URL` — controls backend URL (empty = same origin)
- OpenAPI spec at `http://localhost:8000/openapi.json` (also `/docs` for interactive UI)

See `docs/API_CONTRACT.md` for the complete endpoint reference.

---

## Pipeline Component Details

### Provider system (`src/providers.py`)
Job sources are pluggable modules that implement the `JobProvider` protocol. The orchestrator (`src/main.py`) looks up the requested provider from `PROVIDER_REGISTRY` and calls `fetch_jobs()` — it has no source-specific logic. Built-in providers: `HybridProvider`, `AggregatorProvider`, `LocalATSProvider`. The registry is exposed via `GET /api/pipeline/providers` so the web UI can render provider cards dynamically without hard-coding source names. See `docs/PROVIDERS.md` for the full extension guide.

### Collector (`src/collector.py`)
Implements the ATS fetching logic wrapped by `LocalATSProvider`. Async with aiohttp, 5-concurrent semaphore, 10s timeout. Fetches from:
- **Greenhouse**: `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`
- **Lever**: `GET https://api.lever.co/v0/postings/{slug}?mode=json`
- **Ashby**: `POST https://api.ashbyhq.com/posting-api/job-board/{slug}`
- **Workable**: `GET https://apply.workable.com/api/v1/widget/{slug}`

### Pre-filter (`src/prefilter.py`)
Regex-based pass before LLM. Filters by title patterns (split into `high_confidence` and `broad` tiers), exclusion patterns, tiered location patterns (`location_patterns` vs `remote_patterns` with `fallback_tier` logic), and description signals. All configurable per profile in `profile.yaml`. This flexible system accurately separates direct location matches from remote fallbacks before LLM processing.

### Scorer (`src/scorer.py`)
Claude Haiku 4.5 with prompt caching. System prompt (instructions + CV) is cached → ~90% cost reduction on subsequent calls in the same session.

### Store (`src/store.py`)
SQLite via Python `sqlite3`. Uses context-managed connections (`with self._connect() as conn:`). Key methods added for the web API: `get_jobs_filtered()`, `get_job_detail()`, `get_stats()`, `get_trends()`.

---

## Migration Path (Phase 2)

When ready to replace the Python backend with TypeScript:

1. Port `src/*.py` to `web/src/lib/pipeline/*.ts`
2. Add `web/src/app/api/` route handlers implementing the same REST contract
3. Add Drizzle ORM with the same SQLite schema
4. Set `NEXT_PUBLIC_API_URL=` (empty = same-origin Next.js API routes)
5. Delete `api/` and `src/`

The frontend changes nothing. See `docs/MIGRATION.md` for details.

---

## ATS API Notes

1. **Ashby**: POST endpoint, not GET. May change without notice — treat as best-effort.
2. **Workable**: Widget API returns no descriptions. Scoring is title + location only.
3. **Greenhouse**: `content` field is raw HTML. Stripped with stdlib `html.parser`.
4. **Lever**: `descriptionPlain` can be null. Falls back to empty string.
5. **Dead slugs**: Companies change ATS providers. Logged at WARNING, never crash on 404.
