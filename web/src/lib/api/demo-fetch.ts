import { BASE_PATH } from '@/lib/demo-mode'
import type { components } from './types'

type JobListResponse = components['schemas']['JobListResponse']
type JobDetailResponse = components['schemas']['JobDetailResponse']
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
    return json(await loadJson<JobDetailResponse>(`jobs/${jobDetailMatch[1]}.json`))
  }

  if (url.pathname === '/api/jobs') {
    const dataset = await loadJson<JobListResponse>('jobs.json')
    return json(await applyJobFilters(dataset, url.searchParams))
  }

  if (url.pathname === '/api/stats/trends') {
    return json(await loadJson('stats-trends.json'))
  }

  if (url.pathname === '/api/stats/market') {
    return json(await loadJson('stats-market.json'))
  }

  if (url.pathname === '/api/stats/dismissed') {
    return json(await loadJson('stats-dismissed.json'))
  }

  if (url.pathname === '/api/stats/insights') {
    return json(await loadJson('stats-insights.json'))
  }

  if (url.pathname === '/api/stats') {
    return json(await loadJson('stats.json'))
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
    const snapshot = await loadJson<{ generated_at: string; job_count: number }>('snapshot.json')
    return json({
      live_updated_at: snapshot.generated_at,
      local_updated_at: snapshot.generated_at,
      is_up_to_date: true,
      total_jobs: snapshot.job_count,
    })
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
