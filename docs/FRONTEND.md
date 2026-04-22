# Frontend — Job Radar

Job Radar uses Next.js App Router with a typed API client. All network calls go through `web/src/lib/api/client.ts` or demo-mode equivalents in `web/src/lib/api/demo-fetch.ts`.

## Stack

| Tool | Purpose |
|---|---|
| Next.js 16 | App Router, static export |
| React 19 | UI runtime |
| TypeScript | Type safety |
| openapi-fetch | Typed REST client |
| Tailwind CSS 4 | Styling |
| shadcn/ui | Dialogs, buttons, cards, menus, fields |
| lucide-react | Icons |
| Recharts | Stats page charts |
| sonner | Toasts |

## Frontend Structure

```text
web/src/
├── app/
│   ├── page.tsx                 # Dashboard
│   ├── jobs/
│   ├── applications/
│   ├── stats/
│   ├── companies/
│   └── settings/
├── components/
│   ├── applications/           # Tracker UI, dialogs, list items
│   ├── jobs/                   # Job board + job detail views
│   ├── score/                  # Score-specific presentation
│   ├── wizard/                 # Guided onboarding/edit flow
│   └── ui/                     # shadcn/ui primitives
└── lib/
    ├── api/
    ├── applications/
    ├── jobs/
    └── utils/
```

## Shared UI Patterns

These are worth documenting because they are reused across multiple surfaces and encode stable presentation rules.

### Score presentation

Score-related components live under `web/src/components/score/`.

Common patterns:
- `ScoreRing` is the primary compact score treatment for job cards and application items
- score color semantics stay consistent across the app: high is green, medium is amber, low is red
- score reasoning and key matches stay secondary to the numeric score and title

### Status and priority presentation

There are two separate status systems in the UI:
- board status: discovery workflow state such as `new`, `scored`, `dismissed`
- tracker status: application lifecycle state such as `applied`, `screening`, `offer`, `rejected_by_company`

Priority styling comes from score-derived `apply_priority` and should not be conflated with tracker stage or board status.

### Detail-page card pattern

Large detail surfaces follow a repeatable structure:
- compact uppercase eyebrow label
- card body with the main action surface
- secondary actions in overflow menus when they are not part of the primary path

The application tracker now follows this pattern with `Application Journey` and `Notes` as paired cards.

## URL Structure

Main routes:
- `/` dashboard
- `/jobs` job board
- `/jobs/detail?id=123` job detail
- `/applications` application tracker
- `/stats` analytics
- `/companies` tracked ATS companies
- `/settings` profile editing and guided edit

Common board query params:
- `status`
- `tracked_mode`
- `min_score`
- `max_score`
- `priority`
- `company`
- `search`
- `sort`
- `order`
- `page`
- `per_page`
- `days`

The applications page currently uses query-driven API fetches for:
- `status`
- `search`
- `sort`
- `order`
- `page`
- `per_page`

## Page Surface

### Dashboard `/`

Primary overview page for pipeline freshness and top-level stats.

Main data:
- `GET /api/stats`
- `GET /api/stats/trends`
- `GET /api/jobs` for top matches

### Job Board `/jobs`

Discovery workflow for fetched jobs.

Key behaviors:
- filter by board status, score, company, search term, days, and tracking mode
- trigger rescoring
- move into the tracker from job detail
- keep filters bookmarkable via URL params

### Job Detail `/jobs/detail?id=...`

This page now combines:
- job metadata
- score explanation
- board actions
- application tracker

Tracker UI in the detail view:
- `Application Journey` card
- `Notes` card
- overflow menu for secondary actions
- timeline edit mode

Current tracker interaction model:
- `Update Outcome` appears inline on the latest relevant completed step
- `Add Step` opens a chooser for `Completed` vs `Upcoming`
- `Close Application` is a first-class action from the overflow menu
- response-date editing is done from the `Responded` timeline row in edit mode
- destructive removal of tracker history stays inside the overflow menu

The journey and notes panels are sized together on desktop, with the journey panel capped and internally scrollable.

### Applications `/applications`

Dedicated application-tracking page backed by:
- `GET /api/applications`
- `GET /api/applications/stats`

Page responsibilities:
- separate active applications, offers, and closed outcomes
- search tracked applications
- sort by next stage, applied date, company, or status
- show tracker-focused KPI cards
- launch URL/manual import

### Stats `/stats`

Analytics and reporting page for:
- daily activity
- score trends
- top skills
- company activity
- dismissed reasons
- market intelligence
- optional LLM-generated insights

### Companies `/companies`

Curated ATS source management for the `local` provider.

### Settings `/settings`

Two modes:
- raw editing of profile files
- guided edit flow that reuses saved wizard state

## Tracker Components

The application tracker UI now lives primarily under `web/src/components/applications/`.

Core list and detail components:
- `ApplicationFilters.tsx`
- `ApplicationListItem.tsx`
- `ApplicationStats.tsx`
- `StatusTimeline.tsx`
- `NotesEditor.tsx`

Tracker dialogs and editors:
- `ImportJobDialog.tsx`
- `AddStepDialog.tsx`
- `CompleteStageDialog.tsx`
- `ScheduleNextStageDialog.tsx`
- `AppliedResponseDialog.tsx`
- `NegativeOutcomeDialog.tsx`
- `ResponseMilestoneDialog.tsx`
- `StageEditorDialog.tsx`
- `StageEditorFields.tsx`

Job-detail integration:
- `JobDetailView.tsx` owns tracker fetches, mutations, dialog state, and layout

## Applications Page UX

### `ApplicationFilters`

Controls:
- group chips: `Active`, `Offers`, `Closed`, `All`
- free-text search across title, company, and notes
- status dropdown
- sort dropdown

### `ApplicationStats`

Top summary cards:
- active applications
- offers
- response rate
- average time to response

Secondary summary:
- total tracked applications
- pipeline vs manual source split

### `ApplicationListItem`

Each item shows:
- tracker status badge
- source badge (`Pipeline` or `Manual`)
- board status badge
- title, company, location
- applied date
- latest step when it differs from canonical status
- next scheduled step summary
- score ring when scoring data exists

## Job Detail Tracker UX

### `Application Journey`

The timeline is now the primary tracker surface.

Current rules:
- canonical phase badges were removed from the read view
- only contextual pills like `Latest` and `Next` remain
- `Update Outcome` is the shortcut for positive/negative progression
- scheduled items are visually labeled as upcoming
- timeline rows can expand notes when present

### Edit mode

When `Edit Timeline` is enabled:
- a visible toolbar appears inside the card
- `Add Step` and `Done` are side by side
- edit actions are available directly on rows
- response-date editing lives on the `Responded` row instead of a separate header action

### Notes

`NotesEditor` supports:
- inline notes editing on desktop
- dialog editing on narrow viewports
- dedicated save action

## Demo Mode

The static demo emulates selected API responses in the browser.

Current demo coverage includes:
- `/api/jobs`
- `/api/jobs/{id}`
- `/api/jobs/{id}/timeline`
- `/api/applications`
- `/api/applications/stats`
- `/api/stats` and related stats payloads

Demo-specific behavior:
- dates are rebased relative to the latest demo dataset timestamp
- tracker fields from snapshot job payloads are converted into applications and timeline responses
- dashboard “today” counters are recalculated from the rebased dataset, not just replayed from stale raw values

## State and Data Flow

General rules:
- page-level containers fetch data
- reusable components stay mostly presentational
- typed API responses come from generated OpenAPI types
- refresh events such as pipeline completion fan out through window events and local state refreshes

Tracker-specific flow in job detail:
- fetch job detail
- fetch timeline
- mutate timeline or tracker projection endpoints
- refresh detail and timeline state
- reflect derived tracker summaries back into board and applications views

## Next.js Configuration and Env

The frontend is built as a static export and served by FastAPI in production.

Key configuration points:
- Next.js uses App Router
- production output is exported statically
- local development proxies API traffic to FastAPI
- demo mode swaps normal API fetches for `demo-fetch.ts` lookups

Important env shape:
- `NEXT_PUBLIC_API_URL`
  - in local development this usually points to `http://localhost:8000`
  - in production it can be empty so the app uses same-origin API calls

The typed client should remain the default integration path. Components should not call `fetch` directly unless there is a very specific need.

## Development Commands

From the repo root:
- `make dev` starts FastAPI and Next.js together
- `make build` builds the frontend static export
- `make lint` runs frontend lint and TypeScript checks
- `make types` regenerates frontend API types from OpenAPI

From `web/` directly:
- `npm run dev`
- `npm run build`
- `npm run lint`
- `npx tsc --noEmit`

## Maintenance Notes

1. If backend tracker models or endpoints change, regenerate types with `make types`.
2. When demo behavior changes, update both `scripts/build_demo_snapshot.py` and `web/src/lib/api/demo-fetch.ts`.
3. Keep board status language separate from tracker status language in the UI.
