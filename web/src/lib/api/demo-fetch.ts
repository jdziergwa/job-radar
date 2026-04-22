import { BASE_PATH } from '@/lib/demo-mode'
import type { components } from './types'

type JobListResponse = components['schemas']['JobListResponse']
type JobDetailResponse = components['schemas']['JobDetailResponse']
type JobResponse = components['schemas']['JobResponse']
type ApplicationJobResponse = components['schemas']['ApplicationJobResponse']
type ApplicationListResponse = components['schemas']['ApplicationListResponse']
type ApplicationStatsResponse = components['schemas']['ApplicationStatsResponse']
type ApplicationEventResponse = components['schemas']['ApplicationEventResponse']
type TimelineResponse = components['schemas']['TimelineResponse']
type StatsOverviewResponse = components['schemas']['StatsOverview'] & {
  last_pipeline_run_at?: string | null
}
type TrendsResponse = components['schemas']['TrendsResponse']
type InsightsResponse = components['schemas']['InsightsResponse']
type SnapshotResponse = {
  generated_at: string
  job_count: number
}
type AggregatorStatusResponse = {
  live_updated_at: string | null
  local_updated_at: string | null
  is_up_to_date: boolean
  total_jobs: number
}
type DemoProfileTemplateResponse = {
  profile_yaml: string
  profile_doc: string
}
type DemoWizardStateResponse = {
  profile_name: string
  cv_analysis: components['schemas']['CVAnalysisResponse'] | null
  user_preferences: components['schemas']['UserPreferences'] | null
}

const jsonCache = new Map<string, Promise<unknown>>()
const textCache = new Map<string, Promise<string>>()
const APPLICATION_STATUS_LABELS: Record<string, string> = {
  applied: 'Applied',
  screening: 'Screening',
  interviewing: 'Interviewing',
  offer: 'Offer',
  accepted: 'Accepted',
  rejected_by_company: 'Rejected',
  rejected_by_user: 'Withdrawn',
  ghosted: 'Ghosted',
}

function isDateOnly(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value)
}

function shiftDateValue(value: string | null | undefined, deltaMs: number): string | null | undefined {
  if (!value) {
    return value
  }

  if (isDateOnly(value)) {
    const timestamp = Date.parse(`${value}T00:00:00.000Z`)
    if (Number.isNaN(timestamp)) {
      return value
    }
    return new Date(timestamp + deltaMs).toISOString().slice(0, 10)
  }

  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) {
    return value
  }

  return new Date(timestamp + deltaMs).toISOString()
}

function parseDemoTimestamp(value: string | null | undefined): number | null {
  if (!value) {
    return null
  }

  const timestamp = Date.parse(isDateOnly(value) ? `${value}T00:00:00.000Z` : value)
  return Number.isNaN(timestamp) ? null : timestamp
}

function rebaseJob<T extends JobResponse | JobDetailResponse>(job: T, deltaMs: number): T {
  return {
    ...job,
    posted_at: shiftDateValue(job.posted_at, deltaMs),
    first_seen_at: shiftDateValue(job.first_seen_at, deltaMs) ?? job.first_seen_at,
    last_seen_at: shiftDateValue(job.last_seen_at, deltaMs),
    scored_at: shiftDateValue(job.scored_at, deltaMs),
    applied_at: shiftDateValue(job.applied_at, deltaMs) ?? job.applied_at,
    next_stage_date: shiftDateValue(job.next_stage_date, deltaMs) ?? job.next_stage_date,
  }
}

function rebaseApplicationEvent(event: ApplicationEventResponse, deltaMs: number): ApplicationEventResponse {
  return {
    ...event,
    occurred_at: shiftDateValue(event.occurred_at, deltaMs) ?? event.occurred_at,
    scheduled_for: shiftDateValue(event.scheduled_for, deltaMs) ?? event.scheduled_for,
    created_at: shiftDateValue(event.created_at, deltaMs) ?? event.created_at,
  }
}

function getApplicationStageLabel(status: string | null | undefined): string {
  if (!status) {
    return ''
  }

  return APPLICATION_STATUS_LABELS[status] ?? status.replaceAll('_', ' ').replace(/\b\w/g, (match) => match.toUpperCase())
}

function daysSince(value: string | null | undefined): number | null {
  const timestamp = parseDemoTimestamp(value)
  if (timestamp === null) {
    return null
  }

  const now = new Date()
  const applied = new Date(timestamp)
  const diffMs = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
    - Date.UTC(applied.getUTCFullYear(), applied.getUTCMonth(), applied.getUTCDate())

  return Math.max(0, Math.floor(diffMs / (24 * 60 * 60 * 1000)))
}

function buildApplicationJob(job: JobResponse | JobDetailResponse): ApplicationJobResponse | null {
  if (!job.application_status) {
    return null
  }

  return {
    ...job,
    latest_stage_label: getApplicationStageLabel(job.application_status),
    days_since_applied: daysSince(job.applied_at),
  }
}

function buildApplicationTimeline(job: JobDetailResponse): TimelineResponse {
  if (!job.application_status) {
    return { events: [] }
  }

  const appliedAt = job.applied_at || job.first_seen_at
  const events: ApplicationEventResponse[] = [
    {
      id: job.id * 1000 + 1,
      job_id: job.id,
      event_type: 'stage',
      lifecycle_state: 'completed',
      canonical_phase: 'applied',
      stage_label: 'Applied',
      occurred_at: appliedAt,
      scheduled_for: null,
      status: 'applied',
      note: null,
      created_at: appliedAt,
    },
  ]

  if (job.next_stage_label || job.next_stage_date || job.next_stage_canonical_phase) {
    const scheduledFor = job.next_stage_date || appliedAt
    events.push({
      id: job.id * 1000 + 2,
      job_id: job.id,
      event_type: 'stage',
      lifecycle_state: 'scheduled',
      canonical_phase: (job.next_stage_canonical_phase as ApplicationEventResponse['canonical_phase'] | null) ?? 'screening',
      stage_label: job.next_stage_label || getApplicationStageLabel(job.next_stage_canonical_phase || 'screening'),
      occurred_at: null,
      scheduled_for: scheduledFor,
      status: job.next_stage_canonical_phase || 'screening',
      note: job.next_stage_note || null,
      created_at: scheduledFor,
    })
  }

  return { events }
}

function filterApplicationJobs(
  jobs: ApplicationJobResponse[],
  params: URLSearchParams,
): ApplicationListResponse {
  let filteredJobs = [...jobs]
  const status = params.get('status')
  const search = params.get('search')?.toLowerCase().trim()
  const sort = params.get('sort') || 'next_stage_date'
  const order = params.get('order') === 'desc' ? 'desc' : 'asc'
  const page = Math.max(1, parseOptionalInt(params.get('page')) || 1)
  const perPage = Math.max(1, parseOptionalInt(params.get('per_page')) || 50)

  if (status) {
    const allowed = new Set(status.split(',').map((value) => value.trim()).filter(Boolean))
    filteredJobs = filteredJobs.filter((job) => job.application_status && allowed.has(job.application_status))
  }

  if (search) {
    filteredJobs = filteredJobs.filter((job) =>
      [job.title, job.company_name, job.notes || '']
        .join(' ')
        .toLowerCase()
        .includes(search)
    )
  }

  const sortMap: Record<string, keyof ApplicationJobResponse> = {
    applied_date: 'applied_at',
    company: 'company_name',
    status: 'application_status',
    next_stage_date: 'next_stage_date',
    next_step_date: 'next_stage_date',
  }
  const sortField = sortMap[sort] ?? 'next_stage_date'

  filteredJobs.sort((left, right) => compareNullable(
    left[sortField] as string | number | null | undefined,
    right[sortField] as string | number | null | undefined,
    order,
  ))

  const total = filteredJobs.length
  const pages = Math.max(1, Math.ceil(total / perPage))
  const offset = (page - 1) * perPage

  return {
    jobs: filteredJobs.slice(offset, offset + perPage),
    total,
    page,
    pages,
    per_page: perPage,
  }
}

function buildApplicationStats(jobs: ApplicationJobResponse[]): ApplicationStatsResponse {
  const statusCounts: Record<string, number> = {
    applied: 0,
    screening: 0,
    interviewing: 0,
    offer: 0,
    accepted: 0,
    rejected_by_company: 0,
    rejected_by_user: 0,
    ghosted: 0,
  }
  const companyStats = new Map<string, { applications: number; furthest_stage: string; avg_scores: number[] }>()

  for (const job of jobs) {
    if (job.application_status && job.application_status in statusCounts) {
      statusCounts[job.application_status] += 1
    }

    const existing = companyStats.get(job.company_name) ?? {
      applications: 0,
      furthest_stage: getApplicationStageLabel(job.application_status),
      avg_scores: [],
    }
    existing.applications += 1
    existing.furthest_stage = getApplicationStageLabel(job.application_status)
    if (typeof job.fit_score === 'number') {
      existing.avg_scores.push(job.fit_score)
    }
    companyStats.set(job.company_name, existing)
  }

  const activeCount = jobs.filter((job) => ['applied', 'screening', 'interviewing'].includes(job.application_status || '')).length
  const offersCount = jobs.filter((job) => ['offer', 'accepted'].includes(job.application_status || '')).length
  const pipelineCount = jobs.filter((job) => job.source !== 'manual').length
  const manualCount = jobs.filter((job) => job.source === 'manual').length
  const topCompanies = [...companyStats.entries()]
    .map(([company_name, data]) => ({
      company_name,
      applications: data.applications,
      furthest_stage: data.furthest_stage,
      avg_score: data.avg_scores.length > 0
        ? Number((data.avg_scores.reduce((sum, score) => sum + score, 0) / data.avg_scores.length).toFixed(1))
        : null,
    }))
    .sort((left, right) => {
      const scoreDelta = (right.avg_score ?? -1) - (left.avg_score ?? -1)
      return right.applications - left.applications || scoreDelta
    })
    .slice(0, 5)

  return {
    total: jobs.length,
    active_count: activeCount,
    offers_count: offersCount,
    response_rate: jobs.length > 0
      ? Number(((jobs.filter((job) => (job.application_status || '') !== 'applied').length / jobs.length) * 100).toFixed(1))
      : 0,
    avg_time_to_response_days: null,
    status_counts: statusCounts,
    weekly_velocity: [],
    funnel: {
      applied: statusCounts.applied,
      screening: statusCounts.screening,
      interviewing: statusCounts.interviewing,
      offer: statusCounts.offer,
      accepted: statusCounts.accepted,
    },
    outcome_breakdown: {
      offer: statusCounts.offer,
      accepted: statusCounts.accepted,
      rejected_by_company: statusCounts.rejected_by_company,
      rejected_by_user: statusCounts.rejected_by_user,
      ghosted: statusCounts.ghosted,
    },
    source_breakdown: {
      pipeline: pipelineCount,
      manual: manualCount,
    },
    top_companies: topCompanies,
  }
}

function rebaseJobListResponse(data: JobListResponse, deltaMs: number): JobListResponse {
  return {
    ...data,
    jobs: data.jobs.map((job) => rebaseJob(job, deltaMs)),
  }
}

function rebaseStatsResponse(data: StatsOverviewResponse, deltaMs: number): StatsOverviewResponse {
  return {
    ...data,
    last_pipeline_run_at: shiftDateValue(data.last_pipeline_run_at, deltaMs),
  }
}

function buildDemoStatsResponse(data: StatsOverviewResponse, jobs: JobResponse[], deltaMs: number): StatsOverviewResponse {
  const todayThreshold = Date.UTC(
    new Date().getUTCFullYear(),
    new Date().getUTCMonth(),
    new Date().getUTCDate(),
  )
  const weekAgoThreshold = Date.now() - 7 * 24 * 60 * 60 * 1000

  let newToday = 0
  let totalNewToday = 0
  let highPriorityToday = 0
  let newThisWeek = 0
  let scored = 0
  let applied = 0
  let dismissed = 0
  let pending = 0
  let closed = 0

  const scoreDistribution: StatsOverviewResponse['score_distribution'] = {
    '90-100': 0,
    '80-89': 0,
    '70-79': 0,
    '60-69': 0,
    '50-59': 0,
    'below-50': 0,
  }
  const applyPriorityCounts: StatsOverviewResponse['apply_priority_counts'] = {
    high: 0,
    medium: 0,
    low: 0,
    skip: 0,
  }

  for (const job of jobs) {
    const firstSeenTimestamp = parseDemoTimestamp(job.first_seen_at)
    const isNewToday = firstSeenTimestamp !== null && firstSeenTimestamp >= todayThreshold
    const isNewThisWeek = firstSeenTimestamp !== null && firstSeenTimestamp >= weekAgoThreshold
    const applyPriority = job.score_breakdown?.apply_priority
    const fitScore = job.fit_score

    if (isNewToday) {
      totalNewToday += 1
      if (job.status !== 'dismissed') {
        newToday += 1
      }
      if (applyPriority === 'high') {
        highPriorityToday += 1
      }
    }

    if (isNewThisWeek && job.status !== 'dismissed') {
      newThisWeek += 1
    }

    if (job.scored_at) {
      scored += 1
    }
    if (job.application_status) {
      applied += 1
    }
    if (job.status === 'dismissed') {
      dismissed += 1
    }
    if (job.status === 'new') {
      pending += 1
    }
    if (job.status === 'closed') {
      closed += 1
    }

    if (typeof fitScore === 'number') {
      if (fitScore >= 90) scoreDistribution['90-100'] += 1
      else if (fitScore >= 80) scoreDistribution['80-89'] += 1
      else if (fitScore >= 70) scoreDistribution['70-79'] += 1
      else if (fitScore >= 60) scoreDistribution['60-69'] += 1
      else if (fitScore >= 50) scoreDistribution['50-59'] += 1
      else scoreDistribution['below-50'] += 1
    }

    if (applyPriority && applyPriority in applyPriorityCounts) {
      applyPriorityCounts[applyPriority] += 1
    }
  }

  return {
    ...data,
    total_jobs: jobs.length,
    new_today: newToday,
    total_new_today: totalNewToday,
    high_priority_today: highPriorityToday,
    new_this_week: newThisWeek,
    last_pipeline_run_at: shiftDateValue(data.last_pipeline_run_at, deltaMs),
    scored,
    applied,
    dismissed,
    pending,
    closed,
    score_distribution: scoreDistribution,
    apply_priority_counts: applyPriorityCounts,
  }
}

function rebaseTrendsResponse(data: TrendsResponse, deltaMs: number): TrendsResponse {
  return {
    ...data,
    daily_counts: data.daily_counts.map((entry) => ({
      ...entry,
      date: shiftDateValue(entry.date, deltaMs) ?? entry.date,
    })),
    company_stats: data.company_stats.map((entry) => ({
      ...entry,
      last_seen: shiftDateValue(entry.last_seen, deltaMs) ?? entry.last_seen,
    })),
    score_trend: data.score_trend.map((entry) => {
      if (!entry || typeof entry !== 'object' || !('date' in entry)) {
        return entry
      }

      const nextDate =
        typeof entry.date === 'string' ? shiftDateValue(entry.date, deltaMs) ?? entry.date : entry.date

      return {
        ...entry,
        date: nextDate,
      }
    }),
  }
}

function rebaseInsightsResponse(data: InsightsResponse, deltaMs: number): InsightsResponse {
  return {
    ...data,
    generated_at: shiftDateValue(data.generated_at, deltaMs) ?? data.generated_at,
  }
}

function rebaseAggregatorStatusResponse(
  data: AggregatorStatusResponse,
  deltaMs: number,
): AggregatorStatusResponse {
  return {
    ...data,
    live_updated_at: shiftDateValue(data.live_updated_at, deltaMs) ?? null,
    local_updated_at: shiftDateValue(data.local_updated_at, deltaMs) ?? null,
  }
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function staticPath(path: string): string {
  return `${BASE_PATH}/demo-data/${path}`
}

async function loadJson<T>(path: string): Promise<T> {
  if (!jsonCache.has(path)) {
    jsonCache.set(
      path,
      fetch(staticPath(path)).then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to load demo data: ${path}`)
        }
        return response.json()
      }),
    )
  }

  return jsonCache.get(path) as Promise<T>
}

async function loadText(path: string): Promise<string> {
  if (!textCache.has(path)) {
    textCache.set(
      path,
      fetch(staticPath(path)).then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to load demo text: ${path}`)
        }
        return response.text()
      }),
    )
  }

  return textCache.get(path) as Promise<string>
}

async function loadProfileContent(path: string): Promise<Response> {
  return json({ content: await loadText(path) })
}

function getLatestDemoDatasetTimestamp(data: JobListResponse): number | null {
  let latestTimestamp: number | null = null

  for (const job of data.jobs) {
    for (const value of [job.first_seen_at, job.last_seen_at, job.scored_at, job.applied_at, job.next_stage_date]) {
      const timestamp = parseDemoTimestamp(value)
      if (timestamp !== null && (latestTimestamp === null || timestamp > latestTimestamp)) {
        latestTimestamp = timestamp
      }
    }
  }

  return latestTimestamp
}

async function getDemoSnapshotDeltaMs(): Promise<number> {
  const dataset = await loadJson<JobListResponse>('jobs.json')
  const latestTimestamp = getLatestDemoDatasetTimestamp(dataset)
  if (latestTimestamp !== null) {
    return Date.now() - latestTimestamp
  }

  const snapshot = await loadJson<SnapshotResponse>('snapshot.json')
  const generatedAt = Date.parse(snapshot.generated_at)
  if (Number.isNaN(generatedAt)) {
    return 0
  }
  return Date.now() - generatedAt
}

function getUrl(input: RequestInfo | URL): URL {
  if (input instanceof URL) {
    return input
  }

  if (typeof input === 'string') {
    return new URL(input, 'http://demo.local')
  }

  return new URL(input.url, 'http://demo.local')
}

function getMethod(input: RequestInfo | URL, init?: RequestInit): string {
  const requestMethod =
    typeof input === 'object' && 'method' in input && input instanceof Request
      ? input.method
      : undefined

  return (init?.method || requestMethod || 'GET').toUpperCase()
}

async function getJsonBody(input: RequestInfo | URL, init?: RequestInit): Promise<unknown> {
  const rawBody =
    init?.body ??
    (typeof input === 'object' && input instanceof Request ? input.clone().body : undefined)

  if (!rawBody) {
    return null
  }

  if (typeof init?.body === 'string') {
    try {
      return JSON.parse(init.body)
    } catch {
      return null
    }
  }

  if (typeof input === 'object' && input instanceof Request) {
    try {
      return await input.clone().json()
    } catch {
      return null
    }
  }

  return null
}

function parseOptionalInt(value: string | null): number | null {
  if (!value) return null
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : null
}

function parseOptionalBool(value: string | null): boolean | null {
  if (value === null) return null
  if (value === 'true') return true
  if (value === 'false') return false
  return null
}

function compareNullable<T extends number | string>(
  left: T | null | undefined,
  right: T | null | undefined,
  order: 'asc' | 'desc',
): number {
  const leftMissing = left === null || left === undefined || left === ''
  const rightMissing = right === null || right === undefined || right === ''

  if (leftMissing && rightMissing) return 0
  if (leftMissing) return 1
  if (rightMissing) return -1

  const direction = order === 'asc' ? 1 : -1

  if (typeof left === 'number' && typeof right === 'number') {
    return (left - right) * direction
  }

  return String(left).localeCompare(String(right)) * direction
}

async function applyJobFilters(
  data: JobListResponse,
  params: URLSearchParams,
): Promise<JobListResponse> {
  let jobs = [...data.jobs]

  const status = params.get('status')
  const minScore = parseOptionalInt(params.get('min_score'))
  const maxScore = parseOptionalInt(params.get('max_score'))
  const priority = params.get('priority')
  const company = params.get('company')?.toLowerCase().trim()
  const search = params.get('search')?.toLowerCase().trim()
  const sort = params.get('sort') || 'score'
  const order = params.get('order') === 'asc' ? 'asc' : 'desc'
  const page = Math.max(1, parseOptionalInt(params.get('page')) || 1)
  const perPage = Math.max(1, parseOptionalInt(params.get('per_page')) || 50)
  const days = parseOptionalInt(params.get('days'))
  const isSparse = parseOptionalBool(params.get('is_sparse'))
  const todayOnly = parseOptionalBool(params.get('today_only'))

  if (status) {
    const allowed = new Set(status.split(',').map((value) => value.trim()).filter(Boolean))
    jobs = jobs.filter((job) => allowed.has(job.status))
  }

  if (minScore !== null) {
    jobs = jobs.filter((job) => (job.fit_score ?? 0) >= minScore)
  }

  if (maxScore !== null) {
    jobs = jobs.filter((job) => (job.fit_score ?? 0) <= maxScore)
  }

  if (priority) {
    jobs = jobs.filter((job) => job.score_breakdown?.apply_priority === priority)
  }

  if (company) {
    jobs = jobs.filter((job) => job.company_name.toLowerCase().includes(company))
  }

  if (days !== null) {
    const threshold = new Date(Date.now() - days * 24 * 60 * 60 * 1000)
    jobs = jobs.filter((job) => {
      const firstSeen = new Date(job.first_seen_at)
      return !Number.isNaN(firstSeen.getTime()) && firstSeen >= threshold
    })
  }

  if (isSparse !== null) {
    jobs = jobs.filter((job) => job.is_sparse === isSparse)
  }

  if (todayOnly === true) {
    const today = new Date().toISOString().slice(0, 10)
    jobs = jobs.filter((job) => job.first_seen_at.slice(0, 10) === today)
  }

  if (search) {
    const detailedJobs = await Promise.all(
      jobs.map(async (job) => ({
        job,
        detail: await loadJson<JobDetailResponse>(`jobs/${job.id}.json`),
      })),
    )

    jobs = detailedJobs
      .filter(({ job, detail }) => {
        const haystack = [
          job.title,
          job.company_name,
          detail.description || '',
        ]
          .join(' ')
          .toLowerCase()

        return haystack.includes(search)
      })
      .map(({ job }) => job)
  }

  jobs.sort((left, right) => {
    switch (sort) {
      case 'date':
        return compareNullable(left.first_seen_at, right.first_seen_at, order)
      case 'company':
        return compareNullable(left.company_name, right.company_name, order)
      case 'salary':
        return compareNullable(left.salary_min, right.salary_min, order)
      case 'score':
      default:
        return compareNullable(left.fit_score, right.fit_score, order)
    }
  })

  const total = jobs.length
  const pages = Math.max(1, Math.ceil(total / perPage))
  const offset = (page - 1) * perPage

  return {
    jobs: jobs.slice(offset, offset + perPage),
    total,
    page,
    pages,
    per_page: perPage,
  }
}

async function handleRead(url: URL): Promise<Response | null> {
  if (/^\/api\/jobs\/rescore\/all$/.test(url.pathname)) {
    return json({ error: 'not found in demo' }, 404)
  }

  const jobDetailMatch = url.pathname.match(/^\/api\/jobs\/(\d+)$/)
  if (jobDetailMatch) {
    const [job, deltaMs] = await Promise.all([
      loadJson<JobDetailResponse>(`jobs/${jobDetailMatch[1]}.json`),
      getDemoSnapshotDeltaMs(),
    ])
    return json(rebaseJob(job, deltaMs))
  }

  const jobTimelineMatch = url.pathname.match(/^\/api\/jobs\/(\d+)\/timeline$/)
  if (jobTimelineMatch) {
    const [job, deltaMs] = await Promise.all([
      loadJson<JobDetailResponse>(`jobs/${jobTimelineMatch[1]}.json`),
      getDemoSnapshotDeltaMs(),
    ])
    const rebasedJob = rebaseJob(job, deltaMs)
    const timeline = buildApplicationTimeline(rebasedJob)
    return json({
      events: timeline.events.map((event) => rebaseApplicationEvent(event, 0)),
    })
  }

  if (url.pathname === '/api/jobs') {
    const [dataset, deltaMs] = await Promise.all([
      loadJson<JobListResponse>('jobs.json'),
      getDemoSnapshotDeltaMs(),
    ])
    return json(await applyJobFilters(rebaseJobListResponse(dataset, deltaMs), url.searchParams))
  }

  if (url.pathname === '/api/applications') {
    const [dataset, deltaMs] = await Promise.all([
      loadJson<JobListResponse>('jobs.json'),
      getDemoSnapshotDeltaMs(),
    ])
    const rebasedJobs = rebaseJobListResponse(dataset, deltaMs)
    const trackedJobs = rebasedJobs.jobs
      .map((job) => buildApplicationJob(job))
      .filter((job): job is ApplicationJobResponse => job !== null)

    return json(filterApplicationJobs(trackedJobs, url.searchParams))
  }

  if (url.pathname === '/api/applications/stats') {
    const [dataset, deltaMs] = await Promise.all([
      loadJson<JobListResponse>('jobs.json'),
      getDemoSnapshotDeltaMs(),
    ])
    const rebasedJobs = rebaseJobListResponse(dataset, deltaMs)
    const trackedJobs = rebasedJobs.jobs
      .map((job) => buildApplicationJob(job))
      .filter((job): job is ApplicationJobResponse => job !== null)

    return json(buildApplicationStats(trackedJobs))
  }

  if (url.pathname === '/api/stats/trends') {
    const [trends, deltaMs] = await Promise.all([
      loadJson<TrendsResponse>('stats-trends.json'),
      getDemoSnapshotDeltaMs(),
    ])
    return json(rebaseTrendsResponse(trends, deltaMs))
  }

  if (url.pathname === '/api/stats/market') {
    return json(await loadJson('stats-market.json'))
  }

  if (url.pathname === '/api/stats/dismissed') {
    return json(await loadJson('stats-dismissed.json'))
  }

  if (url.pathname === '/api/stats/insights') {
    const [insights, deltaMs] = await Promise.all([
      loadJson<InsightsResponse>('stats-insights.json'),
      getDemoSnapshotDeltaMs(),
    ])
    return json(rebaseInsightsResponse(insights, deltaMs))
  }

  if (url.pathname === '/api/stats') {
    const [stats, dataset, deltaMs] = await Promise.all([
      loadJson<StatsOverviewResponse>('stats.json'),
      loadJson<JobListResponse>('jobs.json'),
      getDemoSnapshotDeltaMs(),
    ])
    const rebasedJobs = rebaseJobListResponse(dataset, deltaMs)
    return json(buildDemoStatsResponse(stats, rebasedJobs.jobs, deltaMs))
  }

  if (url.pathname === '/api/pipeline/providers') {
    return json(await loadJson('providers.json'))
  }

  if (url.pathname === '/api/pipeline/active') {
    return json({ running: false, run_id: null })
  }

  if (/^\/api\/pipeline\/status\//.test(url.pathname)) {
    return json({
      status: 'done',
      step: 5,
      step_name: 'Done',
      detail: 'Demo mode uses a static snapshot.',
      duration: 0,
      stats: { scored: 0 },
      skipped_steps: [],
      error: null,
    })
  }

  if (url.pathname === '/api/pipeline/aggregator/status') {
    const [snapshot, deltaMs] = await Promise.all([
      loadJson<SnapshotResponse>('snapshot.json'),
      getDemoSnapshotDeltaMs(),
    ])
    return json(rebaseAggregatorStatusResponse({
      live_updated_at: snapshot.generated_at,
      local_updated_at: snapshot.generated_at,
      is_up_to_date: true,
      total_jobs: snapshot.job_count,
    }, deltaMs))
  }

  if (url.pathname.startsWith('/api/companies/')) {
    return json(await loadJson('companies.json'))
  }

  if (/^\/api\/profile\/.+\/yaml$/.test(url.pathname)) {
    return loadProfileContent('profile-yaml.txt')
  }

  if (/^\/api\/profile\/.+\/doc$/.test(url.pathname)) {
    return loadProfileContent('profile-doc.txt')
  }

  if (/^\/api\/profile\/.+\/scoring-philosophy$/.test(url.pathname)) {
    return loadProfileContent('scoring-philosophy.txt')
  }

  if (url.pathname === '/api/profiles') {
    return json(await loadJson('profiles.json'))
  }

  if (url.pathname === '/api/health') {
    return json(await loadJson('health.json'))
  }

  if (url.pathname === '/api/wizard/template') {
    return json(await loadJson<DemoProfileTemplateResponse>('wizard-template.json'))
  }

  if (url.pathname === '/api/wizard/state') {
    return json(await loadJson<DemoWizardStateResponse>('wizard-state.json'))
  }

  return null
}

async function handleWrite(url: URL, input: RequestInfo | URL, init?: RequestInit): Promise<Response | null> {
  if (url.pathname === '/api/pipeline/run') {
    return json({ run_id: 'demo-pipeline-run' })
  }

  if (url.pathname === '/api/jobs/rescore/all') {
    return json({ run_id: 'demo-rescore-all' })
  }

  const rescoreMatch = url.pathname.match(/^\/api\/jobs\/(\d+)\/rescore$/)
  if (rescoreMatch) {
    return json({ run_id: `demo-rescore-${rescoreMatch[1]}` })
  }

  if (/^\/api\/pipeline\/cancel\//.test(url.pathname)) {
    return json({ status: 'cancelling', demo: true })
  }

  const statusMatch = url.pathname.match(/^\/api\/jobs\/(\d+)\/status$/)
  if (statusMatch) {
    const body = await getJsonBody(input, init)
    const nextStatus =
      body && typeof body === 'object' && 'status' in body && typeof body.status === 'string'
        ? body.status
        : 'scored'
    return json({
      ok: true,
      id: Number(statusMatch[1]),
      status: nextStatus,
      demo: true,
    })
  }

  if (url.pathname === '/api/wizard/analyze-cv') {
    const state = await loadJson<DemoWizardStateResponse>('wizard-state.json')
    return json(state.cv_analysis || null)
  }

  if (url.pathname === '/api/wizard/generate-profile') {
    return json({
      profile_yaml: await loadText('profile-yaml.txt'),
      profile_doc: await loadText('profile-doc.txt'),
    })
  }

  if (url.pathname === '/api/wizard/save-profile') {
    return json({ ok: true, name: 'demo', demo: true })
  }

  if (
    url.pathname.startsWith('/api/companies/') ||
    /^\/api\/profile\/.+\/yaml$/.test(url.pathname) ||
    /^\/api\/profile\/.+\/doc$/.test(url.pathname) ||
    /^\/api\/profile\/.+\/scoring-philosophy$/.test(url.pathname)
  ) {
    return json({ ok: true, demo: true })
  }

  return json({ ok: true, demo: true })
}

export const demoFetch: typeof fetch = async (input, init) => {
  const url = getUrl(input)
  const method = getMethod(input, init)

  if (method === 'GET' || method === 'HEAD') {
    const response = await handleRead(url)
    return response ?? json({ error: 'not found in demo' }, 404)
  }

  return (await handleWrite(url, input, init)) ?? json({ ok: true, demo: true })
}
