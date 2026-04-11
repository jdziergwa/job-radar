export const APP_SCROLL_CONTAINER_ID = 'app-scroll-container'
const JOB_BOARD_SCROLL_RESTORE_KEY = 'job-board:restore'

export type JobBoardState = {
  page: number
  status: string
  sort: string
  minScore: string
  search: string
  todayOnly: boolean
  isSparse: boolean | null
}

export const DEFAULT_JOB_BOARD_STATE: JobBoardState = {
  page: 1,
  status: 'new,scored,applied',
  sort: 'score',
  minScore: '',
  search: '',
  todayOnly: false,
  isSparse: null,
}

export function parseJobBoardState(searchParams: URLSearchParams): JobBoardState {
  const rawPage = parseInt(searchParams.get('page') ?? '1', 10)
  const rawMinScore = searchParams.get('min_score') ?? ''
  const isSparse = rawMinScore === 'sparse'

  return {
    page: Number.isFinite(rawPage) && rawPage > 0 ? rawPage : 1,
    status: searchParams.get('status') || DEFAULT_JOB_BOARD_STATE.status,
    sort: searchParams.get('sort') || DEFAULT_JOB_BOARD_STATE.sort,
    minScore: isSparse ? '' : rawMinScore,
    search: searchParams.get('search') || '',
    todayOnly: searchParams.get('today_only') === 'true',
    isSparse: isSparse ? true : null,
  }
}

export function buildJobBoardHref(state: JobBoardState): string {
  const params = new URLSearchParams()

  if (state.page > 1) params.set('page', String(state.page))
  if (state.status !== DEFAULT_JOB_BOARD_STATE.status) params.set('status', state.status)
  if (state.sort !== DEFAULT_JOB_BOARD_STATE.sort) params.set('sort', state.sort)
  if (state.isSparse) {
    params.set('min_score', 'sparse')
  } else if (state.minScore) {
    params.set('min_score', state.minScore)
  }
  if (state.search) params.set('search', state.search)
  if (state.todayOnly) params.set('today_only', 'true')

  const query = params.toString()
  return query ? `/jobs?${query}` : '/jobs'
}

export function getAppScrollContainer(): HTMLElement | null {
  if (typeof document === 'undefined') return null
  return document.getElementById(APP_SCROLL_CONTAINER_ID)
}

export function saveJobBoardScroll(href: string) {
  if (typeof window === 'undefined') return

  const scrollContainer = getAppScrollContainer()
  if (!scrollContainer) return

  window.sessionStorage.setItem(
    JOB_BOARD_SCROLL_RESTORE_KEY,
    JSON.stringify({
      href,
      scrollTop: scrollContainer.scrollTop,
    })
  )
}

export function getSavedJobBoardScroll(href: string): number | null {
  if (typeof window === 'undefined') return null

  const raw = window.sessionStorage.getItem(JOB_BOARD_SCROLL_RESTORE_KEY)
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as { href?: string; scrollTop?: number }
    if (parsed.href !== href || typeof parsed.scrollTop !== 'number') return null
    return parsed.scrollTop
  } catch {
    return null
  }
}

export function clearSavedJobBoardScroll() {
  if (typeof window === 'undefined') return
  window.sessionStorage.removeItem(JOB_BOARD_SCROLL_RESTORE_KEY)
}
