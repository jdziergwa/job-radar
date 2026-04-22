# API Contract — Job Radar

All endpoints are prefixed with `/api/`. The source of truth is the FastAPI OpenAPI schema plus the Pydantic models in `api/models.py`. Frontend types are generated into `web/src/lib/api/types.ts` with `make types`.

Base URL:
- Development: `http://localhost:8000`
- Production: same origin

## Core Types

```typescript
type ATSPlatform = 'greenhouse' | 'lever' | 'ashby' | 'workable'
type JobStatus = 'new' | 'scored' | 'dismissed'
type ApplyPriority = 'high' | 'medium' | 'low' | 'skip'
type ApplicationStatus =
  | 'applied'
  | 'screening'
  | 'interviewing'
  | 'offer'
  | 'accepted'
  | 'rejected_by_company'
  | 'rejected_by_user'
  | 'ghosted'

interface ScoreBreakdown {
  dimensions: {
    tech_stack_match: number
    seniority_match: number
    remote_location_fit: number
    growth_potential: number
  }
  key_matches: string[]
  red_flags: string[]
  fit_category?: string | null
  apply_priority: ApplyPriority
}

interface JobResponse {
  id: number
  ats_platform: ATSPlatform
  company_slug: string
  company_name: string
  title: string
  location: string
  url: string
  posted_at?: string | null
  first_seen_at: string
  last_seen_at?: string | null
  fit_score?: number | null
  score_reasoning?: string | null
  score_breakdown?: ScoreBreakdown | null
  scored_at?: string | null
  status: JobStatus
  application_status?: ApplicationStatus | null
  applied_at?: string | null
  notes?: string | null
  next_stage_label?: string | null
  next_stage_date?: string | null
  next_stage_canonical_phase?: ApplicationStatus | null
  next_stage_note?: string | null
  source?: string | null
  dismissal_reason?: string | null
  match_tier?: string | null
  salary?: string | null
  salary_min?: number | null
  salary_max?: number | null
  salary_currency?: string | null
  is_sparse: boolean
  company_quality_signals: string[]
  workplace_type?: string | null
  raw_location?: string | null
}

interface JobDetailResponse extends JobResponse {
  description?: string | null
}

interface JobListResponse {
  jobs: JobResponse[]
  total: number
  page: number
  pages: number
  per_page: number
}

interface StatsOverview {
  total_jobs: number
  new_today: number
  total_new_today: number
  high_priority_today: number
  new_this_week: number
  last_pipeline_run_at?: string | null
  scored: number
  pending: number
  applied: number
  dismissed: number
  closed: number
  score_distribution: Record<string, number>
  apply_priority_counts: Record<string, number>
}

interface ApplicationEventResponse {
  id: number
  job_id: number
  event_type: 'stage' | string
  lifecycle_state: 'completed' | 'scheduled'
  canonical_phase: ApplicationStatus
  stage_label: string
  occurred_at?: string | null
  scheduled_for?: string | null
  status: string
  note?: string | null
  created_at: string
}

interface TimelineResponse {
  events: ApplicationEventResponse[]
}

interface ApplicationJobResponse extends JobResponse {
  days_since_applied?: number | null
  latest_stage_label?: string | null
}

interface ApplicationListResponse {
  jobs: ApplicationJobResponse[]
  total: number
  page: number
  pages: number
  per_page: number
}

interface ApplicationStatsResponse {
  total: number
  active_count: number
  offers_count: number
  response_rate: number
  avg_time_to_response_days?: number | null
  status_counts: Record<string, number>
  weekly_velocity: { week: string; applications: number }[]
  funnel: {
    applied: number
    screening: number
    interviewing: number
    offer: number
    accepted: number
  }
  outcome_breakdown: Record<string, number>
  source_breakdown: Record<string, number>
  top_companies: {
    company_name: string
    applications: number
    furthest_stage: string
    avg_score?: number | null
  }[]
}

interface ImportJobResponse {
  job_id?: number | null
  fetched: boolean
  needs_manual_entry: boolean
  already_tracked: boolean
  job?: JobResponse | null
}
```

Key model split:
- `status` is the board-level state for discovery workflow: `new`, `scored`, `dismissed`
- `application_status` is the tracker state for active applications and outcomes

## Jobs

### `GET /api/jobs`

Paginated job list for the board.

Query parameters:

| Param | Type | Default | Notes |
|---|---|---:|---|
| `profile` | string | `default` | Profile name |
| `status` | string | all | Comma-separated board statuses: `new,scored,dismissed` |
| `tracked_mode` | string | `all` | `all`, `only`, `exclude` |
| `min_score` | int | — | `0-100` |
| `max_score` | int | — | `0-100` |
| `priority` | string | — | `high`, `medium`, `low`, `skip` |
| `company` | string | — | Case-insensitive substring |
| `search` | string | — | Title/company search |
| `sort` | string | `score` | `score`, `date`, `company` |
| `order` | string | `desc` | `asc`, `desc` |
| `page` | int | `1` | Minimum `1` |
| `per_page` | int | `50` | Maximum `200` |
| `days` | int | — | First seen within last N days |
| `is_sparse` | bool | — | Filter sparse descriptions |
| `today_only` | bool | — | Restrict to items first seen today |

Response: `JobListResponse`

### `GET /api/jobs/{job_id}`

Single job with full description.

Response: `JobDetailResponse`

### `DELETE /api/jobs/{job_id}`

Hard-deletes a manually imported job. Only allowed when `source === "manual"`.

Response:

```json
{ "ok": true, "id": 42 }
```

### `PATCH /api/jobs/{job_id}/status`

Updates the board-level job state.

Body:

```json
{ "status": "dismissed" }
```

Allowed values: `new`, `scored`, `dismissed`

### `POST /api/jobs/{job_id}/rescore`

Triggers rescoring for a single job.

Response:

```json
{ "run_id": "..." }
```

### `POST /api/jobs/rescore/all`

Triggers bulk rescoring for previously scored jobs.

Response:

```json
{ "run_id": "..." }
```

## Application Tracker

### `GET /api/applications`

Paginated tracked-application list for `/applications`.

Query parameters:

| Param | Type | Default | Notes |
|---|---|---:|---|
| `profile` | string | `default` | Profile name |
| `status` | string | all | Comma-separated application statuses |
| `search` | string | — | Searches title, company, notes |
| `sort` | string | `next_stage_date` | `next_stage_date`, `applied_date`, `company`, `status` |
| `order` | string | `asc` | `asc`, `desc` |
| `page` | int | `1` | Minimum `1` |
| `per_page` | int | `50` | Maximum `200` |

Response: `ApplicationListResponse`

### `GET /api/applications/stats`

Tracker analytics for the applications page.

Response: `ApplicationStatsResponse`

### `PATCH /api/jobs/{job_id}/application-status`

Moves a job into the tracker or advances/closes the tracked application.

Body:

```json
{
  "application_status": "screening",
  "note": "Recruiter phone screen confirmed",
  "occurred_at": "2026-04-22"
}
```

The backend enforces allowed transitions. Invalid transitions return `422`.

### `PATCH /api/jobs/{job_id}/applied-at`

Sets or edits the application date for a tracked job.

Body:

```json
{ "applied_at": "2026-04-15" }
```

### `PATCH /api/jobs/{job_id}/response-date`

Creates or updates the first response milestone.

Body:

```json
{ "response_date": "2026-04-18" }
```

Response: `ApplicationEventResponse`

### `DELETE /api/jobs/{job_id}/application-status`

Removes the job from the tracker and clears derived tracker state.

Response: `JobResponse`

### `PATCH /api/jobs/{job_id}/notes`

Stores tracker notes shown in the job detail notes panel.

Body:

```json
{ "notes": "Prep notes, recruiter context, follow-ups" }
```

### `PATCH /api/jobs/{job_id}/next-stage`

Creates or updates the upcoming scheduled stage.

Body:

```json
{
  "canonical_phase": "interviewing",
  "stage_label": "Technical interview",
  "scheduled_for": "2026-04-25",
  "note": "Panel with EM + senior IC",
  "mark_responded": true,
  "response_date": "2026-04-22"
}
```

If `mark_responded` is true, `response_date` is required.

### `GET /api/jobs/{job_id}/timeline`

Returns the full application timeline, including completed and scheduled events.

Response: `TimelineResponse`

### `POST /api/jobs/{job_id}/timeline`

Adds a completed timeline step.

Body:

```json
{
  "canonical_phase": "interviewing",
  "stage_label": "Take-home task",
  "occurred_at": "2026-04-20",
  "note": "Submitted same day"
}
```

The first completed event for a tracked job must be `applied`.

### `PATCH /api/jobs/{job_id}/timeline/{event_id}`

Edits a timeline event. Depending on event type and lifecycle state, callers can update:
- `canonical_phase`
- `stage_label`
- `occurred_at`
- `scheduled_for`
- `created_at`
- `note`

Response: `ApplicationEventResponse`

### `DELETE /api/jobs/{job_id}/timeline/{event_id}`

Deletes a timeline event. The backend blocks destructive edits that would leave a tracked job without any completed events or without any `applied` event.

Response: `TimelineResponse`

### `POST /api/applications/import`

Imports an application from a job URL. If Job Radar can identify and fetch the job, it either re-tracks an existing row or creates tracker state for it.

Body:

```json
{
  "url": "https://boards.greenhouse.io/acme/jobs/123",
  "applied_at": "2026-04-14",
  "notes": "Applied via referral",
  "track_company_in_pipeline": true
}
```

Response: `ImportJobResponse`

### `POST /api/applications/import/manual`

Manual fallback when URL import cannot fully resolve a job.

Body:

```json
{
  "company_name": "Acme",
  "title": "Senior QA Engineer",
  "location": "Remote EU",
  "url": "https://example.com/jobs/123",
  "applied_at": "2026-04-14",
  "description": "Copied from the job post",
  "notes": "Applied manually",
  "track_company_in_pipeline": false
}
```

Response: `ImportJobResponse`

## Stats

### `GET /api/stats`

Dashboard aggregate counters.

Response: `StatsOverview`

### `GET /api/stats/trends`

Time-series and chart payloads for the stats page.

Query parameters:

| Param | Type | Default |
|---|---|---:|
| `profile` | string | `default` |
| `days` | int | `30` |

### `GET /api/stats/dismissed`

Dismissal reason breakdown.

### `GET /api/stats/market`

Structured market intelligence payload.

### `GET /api/stats/insights`

Cached narrative market insights.

Query parameters:

| Param | Type | Default | Notes |
|---|---|---:|---|
| `profile` | string | `default` | Profile name |
| `days` | int | `30` | Analysis window |
| `force` | bool | `false` | Regenerates via Claude when true |

## Pipeline

### `GET /api/pipeline/providers`

Returns available job source providers for the run dialog.

### `POST /api/pipeline/run`

Starts the pipeline.

Body:

```json
{
  "profile": "default",
  "sources": ["aggregator", "local"],
  "dry_run": false
}
```

### `GET /api/pipeline/status/{run_id}`

Polling endpoint for run progress.

### `POST /api/pipeline/cancel/{run_id}`

Cancels a running pipeline.

### `GET /api/pipeline/active`

Returns active run state for the current profile.

### `GET /api/pipeline/aggregator/status`

Returns the freshness state of the aggregator snapshot.

## Profile, Wizard, Companies

### Profile endpoints

- `POST /api/profile/{name}`
- `GET /api/profiles`
- `GET|PUT /api/profile/{name}/yaml`
- `GET|PUT /api/profile/{name}/doc`
- `GET|PUT /api/profile/{name}/scoring-philosophy`

### Wizard endpoints

- `POST /api/wizard/analyze-cv`
- `POST /api/wizard/generate-profile`
- `POST /api/wizard/refine-profile`
- `POST /api/wizard/save-profile`
- `GET /api/wizard/state`
- `GET /api/wizard/template`

### Company tracking endpoints

- `GET /api/companies/{profile}`
- `POST /api/companies/{profile}`
- `PATCH /api/companies/{profile}/{platform}/{slug}`
- `DELETE /api/companies/{profile}/{platform}/{slug}`

## Notes

- `JobResponse` now carries both board-level data and derived tracker fields.
- Tracker timeline events are the history model; job-level tracker fields are projections used for list and detail views.
- Demo mode implements `/api/applications`, `/api/applications/stats`, `/api/jobs/{id}/timeline`, and rebased `/api/stats` behavior through `web/src/lib/api/demo-fetch.ts`.
