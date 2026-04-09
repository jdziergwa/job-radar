# Frontend — Job Radar

Next.js 16 App Router application (`output: 'export'`). All API calls go through `lib/api/client.ts`. Components never call `fetch` directly.

---

## Tech Stack

| Tool | Version | Purpose |
|------|---------|---------|
| Next.js | 16 | React framework, App Router, static export |
| React | 19 | UI library |
| TypeScript | 5 | Type safety |
| openapi-fetch | 0.17 | Type-safe REST API client |
| Tailwind CSS | 4 | Utility-first styling (`@theme` directive, no config file) |
| shadcn/ui | 4 | Component primitives (Button, Badge, Dialog, Card, Switch...) |
| Recharts | 3.x | Charts (activity, skills, score distribution) |
| lucide-react | latest | Icons |
| next-themes | 0.4 | Dark/light mode |
| sonner | 2.x | Toast notifications |
| marked | 17 | Markdown → HTML (profile_doc.md preview in Settings) |

## Design

- **Glassmorphism**: `bg-background/80 backdrop-blur-md` for panels and navbars
- **Micro-animations**: hover transitions on all interactive elements, animated `ScoreRing` on mount
- **Typography**: Inter for layout text, JetBrains Mono for data/tags/IDs
- **Dark mode default**: stark contrasts, subtle `border-white/10` card borders

### Fonts

- **UI text**: Inter Variable — headings, body, labels
- **Scores and code**: JetBrains Mono — score numbers, YAML editor, IDs

### Color Palette

Defined as CSS custom properties in `globals.css`, swapped per theme.

```css
/* globals.css */
:root {
  --background: 0 0% 100%;
  --foreground: 240 10% 3.9%;
  --card: 0 0% 100%;
  --card-foreground: 240 10% 3.9%;
  --border: 240 5.9% 90%;
  --input: 240 5.9% 90%;
  --primary: 262.1 83.3% 57.8%;    /* violet-600 — brand accent */
  --primary-foreground: 210 20% 98%;
  --muted: 240 4.8% 95.9%;
  --muted-foreground: 240 3.8% 46.1%;
  --radius: 0.5rem;
}

.dark {
  --background: 240 10% 3.9%;
  --foreground: 0 0% 98%;
  --card: 240 10% 3.9%;
  --card-foreground: 0 0% 98%;
  --border: 240 3.7% 15.9%;
  --input: 240 3.7% 15.9%;
  --primary: 263.4 70% 50.4%;
  --primary-foreground: 210 20% 98%;
  --muted: 240 3.7% 15.9%;
  --muted-foreground: 240 5% 64.9%;
}

/* Score tier colors — not from shadcn, defined separately */
:root {
  --score-high: 142 71% 45%;      /* green-500 */
  --score-medium: 38 92% 50%;     /* amber-500 */
  --score-low: 0 84% 60%;         /* red-500 */
}
```

### Score Tiers

```typescript
// web/src/lib/utils/score.ts
export function scoreToColor(score: number): string {
  if (score >= 80) return 'text-green-500'
  if (score >= 60) return 'text-amber-500'
  return 'text-red-500'
}

export function scoreToRingColor(score: number): string {
  if (score >= 80) return '#22c55e'   // green-500
  if (score >= 60) return '#f59e0b'   // amber-500
  return '#ef4444'                     // red-500
}

export function scoreToBadge(score: number): 'default' | 'secondary' | 'destructive' {
  if (score >= 80) return 'default'     // green variant
  if (score >= 60) return 'secondary'   // amber variant
  return 'destructive'                  // red variant
}

export function priorityToColor(priority: string): string {
  const map = {
    high: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    medium: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    low: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    skip: 'bg-red-500/20 text-red-400 border-red-500/30',
  }
  return map[priority as keyof typeof map] ?? map.low
}
```

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌─────────────────────────────────────────────┐   │
│ │          │ │                                              │   │
│ │  Sidebar │ │  Main content area                           │   │
│ │  240px   │ │  max-w-7xl mx-auto px-6                     │   │
│ │          │ │                                              │   │
│ │  nav     │ │                                              │   │
│ │  items   │ │                                              │   │
│ │          │ │                                              │   │
│ └──────────┘ └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

- Sidebar: `w-60` fixed on desktop, collapses to `w-16` icon-only on `< lg`
- On mobile: sidebar becomes a drawer (shadcn Sheet component)
- Content: `flex-1 overflow-auto`

---

## Component Catalogue

### ScoreRing

SVG circle with animated stroke-dashoffset. The signature UX detail of the app.

```
Props:
  score: number       (0-100)
  size?: 'sm' | 'md' (48px or 80px)
  animated?: boolean  (default true)
```

Implementation:
- SVG `<circle>` with `stroke-dasharray` and animated `stroke-dashoffset`
- `dasharray = 2π × r` (full circumference)
- `dashoffset = dasharray × (1 - score/100)` (empty portion)
- CSS transition: `transition: stroke-dashoffset 0.6s ease-out`
- Trigger via `useEffect` with `requestAnimationFrame` to start from 0

```
 ╭──────╮
│  82%  │   ← JetBrains Mono, score color
 ╰──────╯
```

### ScoreBar

Horizontal progress bar for dimension breakdown.

```
Props:
  label: string       e.g. "Tech Stack Match"
  value: number       0-100
  animated?: boolean
```

```
Tech Stack Match    ████████████████████░░░░ 90
Seniority Match     ████████████████░░░░░░░░ 75
Remote Fit          ██████████████████░░░░░░ 82
Growth Potential    ████████████░░░░░░░░░░░░ 60
```

### PriorityBadge

```
Props:
  priority: 'high' | 'medium' | 'low' | 'skip'
```

Renders: `HIGH` / `MED` / `LOW` / `SKIP` with matching background/text colors.

### JobListItem

```
Props:
  job: Job
```

Layout:
┌─────────────────────────────────────────────────────────────────────────────┐
│  ╭────╮  [LV] [SCORED]                                                      │
│  │ 88 │  Senior SDET — Automation Platform                 3 days ago  (>)  │
│  ╰────╯  Datadog · Remote EU                                                │
│  [HIGH]  ✓ Playwright  ✓ CI/CD  ✓ Python                                    │
│          “Strong match for automation...”                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Tags: `key_matches` → green pill badges (max 3 shown, `+N more`)
Reasoning: `score_reasoning` → italicized snippet below the title.
ATS badge: small monospace label (`GH` / `LV` / `AS` / `WK`)

### FilterPanel

```
Props:
  filters: FilterState
  onChange: (filters: FilterState) => void
```

Sections (all collapsible):
- **Score**: dual-handle range slider (0–100), `min_score` and `max_score`
- **Status**: checkboxes (New / Scored / Applied / Dismissed / Closed)
- **Priority**: checkboxes with colored dots (High / Medium / Low / Skip)
- **Search**: keyword text input for filtering jobs by description, title, or company (debounce 300ms)
- **Date**: select (Any / Last 7 days / Last 14 days / Last 30 days)
- **Platform**: checkboxes (Greenhouse / Lever / Ashby / Workable)

Filter state is serialized to URL search params so filters are bookmarkable.

### PipelineDialog

```
State machine:
  idle → running → done | error
```

- **Idle**: "Fetch New Results" button in sidebar triggers dialog open
- **Dialog contents**: Profile selector, Source strategy (Comprehensive Scan, Global Aggregator only, Targeted Boards only), Dry run toggle, Run button. Incorporates data freshness badging.
- **Running**: Step indicators (dots), step name, elapsed time
- **Done**: Stats summary (N new jobs, N scored), "View New Jobs" link
- **Error**: Error message, "Retry" button

Step indicators:
```
● ● ○ ○ ○   Collecting...
● ● ● ○ ○   Pre-filtering...
● ● ● ● ○   Scoring with Claude...
● ● ● ● ●   Done — 4 new matches
```

### StatsCard

```
Props:
  label: string
  value: number | string
  trend?: number    (positive = up, negative = down, for color coding)
  icon?: LucideIcon
```

---

## Pages

### Dashboard (`/`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ New Today│ │This Week │ │ Applied  │ │   Avg Score      │  │
│  │    12    │ │    47    │ │    3     │ │      74          │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
│                                                                  │
│  [Jobs per day — 7 day sparkline chart]                         │
│                                                                  │
│  Top Matches This Week                                           │
│  [HighPriorityTable]                                             │
└─────────────────────────────────────────────────────────────────┘
```

Data: `GET /api/stats` + `GET /api/stats/trends?days=7` + `GET /api/jobs?days=7&sort=score&per_page=5`

### Job Board (`/jobs`)

```
┌────────────────────┬────────────────────────────────────────────┐
│  Filters           │  Sort: Score ▼    47 jobs                  │
│                    │                                             │
│  Score: 60 — 100   │  [JobListItem]                              │
│  ☑ Scored          │  [JobListItem]                              │
│  ☑ New             │  [JobListItem]                              │
│  ☐ Applied         │                                             │
│  ☐ Dismissed       │  ← 1  2  3 →                                │
│                    │                                             │
│  Priority          │                                             │
│  ● High            │                                             │
│  ● Medium          │                                             │
│                    │                                             │
│  Company: _____    │                                             │
└────────────────────┴────────────────────────────────────────────┘
```

The filter panel acts as a sticky left column on desktop, and a sheet/drawer on mobile.
Also includes global actions like `RescoreAllButton` for batch re-evaluating jobs.
URL: `/jobs?search=engineer&status=scored,new&min_score=60&sort=score` — fully bookmarkable.

### Job Detail (`/jobs/[id]`)

```
┌──────────────────────────────────┬─────────────────────────────┐
│  ← Back to jobs                  │                             │
│                                  │  Metadata                   │
│  Senior SDET — Automation Plt    │  Platform: Greenhouse       │
│  Datadog · Remote EU             │  First seen: 3 days ago     │
│  [Applied ✓] [View on ATS ↗] [x] │  Scored: 2 days ago         │
│                                  │  Status: Scored             │
│  ╭────╮  88/100 — Strong match   │                             │
│  │ 88 │  "Mobile automation..."  │  [Mark Applied]             │
│  ╰────╯                          │  [Dismiss]                  │
│                                  │  [View on ATS ↗]            │
│  Tech Stack Match  ████████ 90   │                             │
│  Seniority Match   ██████   75   │                             │
│  Remote Fit        ████████ 82   │                             │
│  Growth Potential  █████    60   │                             │
│                                  │                             │
│  ✓ Playwright  ✓ Python  ✓ CI/CD │                             │
│  ⚠ No Kubernetes experience      │                             │
│                                  │                             │
│  ─── Full Description ───────    │                             │
│  [prose text scrollable]         │                             │
└──────────────────────────────────┴─────────────────────────────┘
```

### Stats & Trends (`/stats`)

Four chart sections stacked vertically:

1. **Jobs per Day** — Recharts LineChart, 30 days, two lines (new jobs + scored jobs), area fill with low opacity
2. **Top Skills** — Recharts HorizontalBarChart, top 20 skills from key_matches aggregation, colored bars (violet)
3. **Score Distribution** — Recharts BarChart, 6 buckets (90-100, 80-89, ..., below-50)
4. **Company Activity** — Sortable table (job count / avg score), company name + counts

### Companies (`/companies`)

```
Tabs: [Greenhouse] [Lever] [Ashby] [Workable]

Add Company
Platform: [Greenhouse ▼]  Slug: [_______]  Name: [_______]  [Add]

─────────────────────────────────────────────────────────────────
Name          Slug           # Jobs   Last Seen    Action
─────────────────────────────────────────────────────────────────
Datadog       datadog        47       2 days ago   [Remove]
Stripe        stripe         12       5 days ago   [Remove]
...
```

### Settings (`/settings`)

Two side-by-side sections:

```
┌──────────────────────────────┬──────────────────────────────────┐
│  search_config.yaml          │  profile_doc.md                  │
│                              │  [Edit] [Preview]                │
│  ┌────────────────────────┐  │                                  │
│  │ keywords:              │  │  [Markdown preview or textarea]  │
│  │   title_patterns:      │  │                                  │
│  │     - "\\bsdet\\b"     │  │                                  │
│  │   ...                  │  │                                  │
│  └────────────────────────┘  │                                  │
│                              │                                  │
│  [Save]  ✓ Saved 2 min ago   │  [Save]                          │
│  ⚠ Invalid YAML (on error)   │                                  │
└──────────────────────────────┴──────────────────────────────────┘
```

YAML editor: monospace textarea, inline error message on invalid YAML.
Markdown editor: textarea with "Preview" toggle (renders via `marked`).

---

## URL Structure

```
/                           Dashboard
/jobs                       Job board (with filter query params)
/jobs?status=scored         Scored jobs only
/jobs?min_score=80          High matches only
/jobs?days=7                Jobs from last 7 days
/jobs/42                    Job detail
/stats                      Stats & trends
/companies                  Company management
/settings                   Profile settings
```

---

## State Management

No global state library. State is managed at three levels:

1. **URL params** — filter state in `/jobs` (bookmarkable, shareable)
2. **React state** — component-local UI state (dialog open/closed, form values)
3. **Server state** — data from API, refreshed on route navigation or after mutations

Pattern for the job board:
```typescript
// Read filters from URL
const searchParams = useSearchParams()
const minScore = Number(searchParams.get('min_score') ?? '0')
const status = searchParams.get('status')?.split(',') ?? []

// Write filters to URL (triggers re-render + refetch)
const router = useRouter()
function updateFilter(key: string, value: string) {
  const params = new URLSearchParams(searchParams)
  params.set(key, value)
  router.push(`/jobs?${params.toString()}`)
}
```

---

## Next.js Configuration

```typescript
// next.config.ts
import type { NextConfig } from 'next'

const config: NextConfig = {
  output: 'export',   // Static HTML export → web/out/ served by FastAPI

  // Dev: proxy /api/* to FastAPI. Not needed in production (FastAPI handles /api).
  // Note: rewrites() does not work with output: 'export' for production,
  // but is applied during `next dev` only.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/:path*`,
      },
    ]
  },
}

export default config
```

---

## Environment Variables

```bash
# web/.env.development.local  (development — gitignored)
NEXT_PUBLIC_API_URL=http://localhost:8000

# web/.env.production.local   (production — gitignored)
NEXT_PUBLIC_API_URL=            # empty = same origin
```

The `NEXT_PUBLIC_` prefix makes the variable available in browser code.
`client.ts` reads it: `const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''`

---

## Development Commands

```bash
cd web

npm run dev       # Start dev server at localhost:3000
npm run build     # Static export to web/out/
npm run lint      # ESLint
npx tsc --noEmit  # Type check without emitting files
```
