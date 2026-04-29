'use client'

import { useCallback, useEffect, useLayoutEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api/client'
import { ImportJobDialog } from '@/components/applications/ImportJobDialog'
import { JobListItem } from '@/components/jobs/JobListItem'
import { DismissalSummary } from '@/components/jobs/DismissalSummary'
import { RescoreAllButton } from '@/components/jobs/RescoreAllButton'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, ChevronDown, ChevronsLeft, ChevronsRight, Loader2, Search, SearchX, SlidersHorizontal, X, HelpCircle, Clock, Plus } from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  buildJobBoardHref,
  clearSavedJobBoardScroll,
  DEFAULT_JOB_BOARD_STATE,
  getAppScrollContainer,
  getSavedJobBoardScroll,
  parseJobBoardState,
  type JobBoardState,
} from '@/lib/jobs/navigation'

const STATUS_OPTIONS = [
  { value: 'new,scored', trackedMode: 'exclude', label: 'Active' },
  { value: 'new', trackedMode: 'exclude', label: 'Unscored' },
  { value: 'scored', trackedMode: 'exclude', label: 'Scored' },
  { value: '', trackedMode: 'only', label: 'Tracked' },
  { value: 'dismissed', trackedMode: 'all', label: 'Dismissed' },
  { value: '', trackedMode: 'all', label: 'Total' },
] as const

const SORT_OPTIONS = [
  { value: 'score', label: 'Score' },
  { value: 'date', label: 'Date' },
  { value: 'company', label: 'Company' },
  { value: 'salary', label: 'Salary' },
]

const SCORE_FILTER_OPTIONS = [
  { value: '', label: 'Any score' },
  { value: '50', label: '50+' },
  { value: '70', label: '70+' },
  { value: '80', label: '80+' },
  { value: '90', label: '90+' },
  { value: 'sparse', label: '?' },
]

export default function JobsPage() {
  const router = useRouter()
  const [jobs, setJobs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(DEFAULT_JOB_BOARD_STATE.page)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(DEFAULT_JOB_BOARD_STATE.status)
  const [trackedMode, setTrackedMode] = useState(DEFAULT_JOB_BOARD_STATE.trackedMode)
  const [sort, setSort] = useState(DEFAULT_JOB_BOARD_STATE.sort)
  const [minScore, setMinScore] = useState(DEFAULT_JOB_BOARD_STATE.minScore)
  const [searchTerm, setSearchTerm] = useState(DEFAULT_JOB_BOARD_STATE.search)
  const [search, setSearch] = useState(DEFAULT_JOB_BOARD_STATE.search)
  const [isSparse, setIsSparse] = useState<boolean | null>(DEFAULT_JOB_BOARD_STATE.isSparse)
  const [todayOnly, setTodayOnly] = useState(DEFAULT_JOB_BOARD_STATE.todayOnly)
  const [statusOpen, setStatusOpen] = useState(false)
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const statusRef = useRef<HTMLDivElement>(null)
  const boardStateRef = useRef<JobBoardState>(DEFAULT_JOB_BOARD_STATE)
  const restoredScrollRef = useRef(false)

  // Close status dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (statusRef.current && !statusRef.current.contains(e.target as Node)) {
        setStatusOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const syncBoardUrl = useCallback((nextState: JobBoardState) => {
    const nextHref = buildJobBoardHref(nextState)
    const currentHref = `${window.location.pathname}${window.location.search}`

    if (nextHref !== currentHref) {
      window.history.replaceState(null, '', nextHref)
    }
  }, [])

  const buildNextState = useCallback((
    pageNum: number,
    overrides: Partial<JobBoardState> = {}
  ): JobBoardState => {
    const currentState = boardStateRef.current

    return {
      page: pageNum,
      status: overrides.status ?? currentState.status,
      trackedMode: overrides.trackedMode ?? currentState.trackedMode,
      sort: overrides.sort ?? currentState.sort,
      minScore: Object.prototype.hasOwnProperty.call(overrides, 'minScore')
        ? overrides.minScore ?? ''
        : currentState.minScore,
      search: Object.prototype.hasOwnProperty.call(overrides, 'search')
        ? overrides.search ?? ''
        : currentState.search,
      todayOnly: Object.prototype.hasOwnProperty.call(overrides, 'todayOnly')
        ? overrides.todayOnly ?? false
        : currentState.todayOnly,
      isSparse: Object.prototype.hasOwnProperty.call(overrides, 'isSparse')
        ? overrides.isSparse ?? null
        : currentState.isSparse,
    }
  }, [])

  const applyBoardState = useCallback((nextState: JobBoardState) => {
    boardStateRef.current = nextState
    setPage(nextState.page)
    setStatus(nextState.status)
    setTrackedMode(nextState.trackedMode)
    setSort(nextState.sort)
    setMinScore(nextState.minScore)
    setSearch(nextState.search)
    setIsSparse(nextState.isSparse)
    setTodayOnly(nextState.todayOnly)
    syncBoardUrl(nextState)
  }, [syncBoardUrl])

  const fetchJobs = useCallback(async (nextState: JobBoardState) => {
    applyBoardState(nextState)
    setLoading(true)
    
    try {
      const query: Record<string, any> = { page: nextState.page, per_page: 15, sort: nextState.sort }
      if (nextState.status) query.status = nextState.status
      if (nextState.trackedMode) query.tracked_mode = nextState.trackedMode
      if (nextState.minScore) query.min_score = parseInt(nextState.minScore, 10)
      if (nextState.search) query.search = nextState.search
      if (nextState.isSparse !== null) query.is_sparse = nextState.isSparse
      if (nextState.todayOnly) query.today_only = true

      const { data } = await api.GET('/api/jobs', { params: { query } })
      if (data) {
        if (data.page !== nextState.page) {
          applyBoardState({ ...nextState, page: data.page })
        }
        setJobs(data.jobs)
        setTotal(data.total)
        setPage(data.page)
        setPages(data.pages)
      }
    } finally {
      setLoading(false)
    }
  }, [applyBoardState])

  useEffect(() => {
    const initialState = parseJobBoardState(new URLSearchParams(window.location.search))

    boardStateRef.current = initialState
    setSearchTerm(initialState.search)
    fetchJobs(initialState)

    // Listen for pipeline completion to refresh job data
    const handleRefresh = () => fetchJobs(boardStateRef.current)
    window.addEventListener('pipeline-finished', handleRefresh)
    return () => window.removeEventListener('pipeline-finished', handleRefresh)
  }, [fetchJobs])

  // Debounced search
  useEffect(() => {
    if (searchTerm === search) return
    
    const timer = setTimeout(() => {
      fetchJobs(buildNextState(1, { search: searchTerm }))
    }, 400)
    
    return () => clearTimeout(timer)
  }, [buildNextState, fetchJobs, search, searchTerm])

  const boardHref = buildJobBoardHref({
    page,
    status,
    trackedMode,
    sort,
    minScore,
    search,
    todayOnly,
    isSparse,
  })

  useLayoutEffect(() => {
    if (loading || restoredScrollRef.current) return

    const savedScrollTop = getSavedJobBoardScroll(boardHref)
    if (savedScrollTop === null) return

    const scrollContainer = getAppScrollContainer()
    if (!scrollContainer) return

    const previousBehavior = scrollContainer.style.scrollBehavior
    scrollContainer.style.scrollBehavior = 'auto'
    scrollContainer.scrollTop = savedScrollTop
    scrollContainer.style.scrollBehavior = previousBehavior

    restoredScrollRef.current = true
    clearSavedJobBoardScroll()
  }, [boardHref, loading])

  const applyStatus = (val: string, nextTrackedMode: JobBoardState['trackedMode']) => {
    fetchJobs(buildNextState(1, { status: val, trackedMode: nextTrackedMode }))
  }

  const applyTodayOnly = (val: boolean) => {
    fetchJobs(buildNextState(1, { todayOnly: val }))
  }

  const applySort = (val: string) => {
    fetchJobs(buildNextState(1, { sort: val }))
  }

  const applyMinScore = (val: string) => {
    if (val === 'sparse') {
      fetchJobs(buildNextState(1, { isSparse: true, minScore: '' }))
    } else {
      fetchJobs(buildNextState(1, { minScore: val, isSparse: null }))
    }
  }

  return (
    <div className="flex flex-col bg-background/30 px-6 py-8">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="mb-6">
          <h1 className="text-2xl font-black tracking-tight text-foreground sm:text-3xl mb-1">
            Job Board
          </h1>
          <p className="text-sm text-muted-foreground">
            {total} opportunities identified for your profile.
          </p>
        </div>

        {status === 'dismissed' && <DismissalSummary />}

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-muted/30 px-3 py-1.5 rounded-full border border-border/50 text-sm font-medium">
            <span className="text-primary font-bold">{total}</span>
            <span className="text-muted-foreground">Jobs Found</span>
          </div>
          <Button
            variant="outline"
            onClick={() => setImportDialogOpen(true)}
            className="gap-2 rounded-full border-border/50 bg-background/50 shadow-sm hover:bg-background/80"
          >
            <Plus className="h-4 w-4" />
            Import Job
          </Button>
          <RescoreAllButton variant="outline" className="rounded-full shadow-sm bg-background/50 hover:bg-background/80" />
        </div>
      </header>

      {/* Search Bar Row */}
      <div className="relative group w-full lg:max-w-2xl mb-6">
        <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
          <Search className="h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
        </div>
        <input
          type="text"
          placeholder="Search keywords in title, company, or description..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-card/40 backdrop-blur-md border border-border/40 hover:border-border/80 focus:border-primary/50 focus:ring-4 focus:ring-primary/5 h-12 pl-11 pr-12 rounded-2xl text-sm font-medium transition-all outline-none"
        />
        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            className="absolute inset-y-0 right-4 flex items-center text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Filter Bar Row */}
      <div className="relative z-10 flex flex-wrap items-center gap-3 p-4 rounded-2xl border border-border/40 bg-card/30 backdrop-blur-sm shadow-sm mb-6">
        <SlidersHorizontal className="h-4 w-4 text-muted-foreground shrink-0" />

        {/* Status filter dropdown */}
        <div className="relative" ref={statusRef}>
          <button
            onClick={() => setStatusOpen(!statusOpen)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-all border bg-primary text-primary-foreground border-primary shadow-sm cursor-pointer"
          >
            {STATUS_OPTIONS.find((o) => o.value === status && o.trackedMode === trackedMode)?.label || 'Active'}
            <ChevronDown className={`h-3 w-3 text-muted-foreground transition-transform ${statusOpen ? 'rotate-180' : ''}`} />
          </button>
          {statusOpen && (
            <div className="absolute top-full left-0 mt-2 min-w-[140px] rounded-xl border border-border/50 bg-popover shadow-2xl z-50 overflow-hidden py-1 animate-in fade-in slide-in-from-top-1 duration-150">
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={`${opt.label}-${opt.value}-${opt.trackedMode}`}
                  onClick={() => { applyStatus(opt.value, opt.trackedMode); setStatusOpen(false) }}
                  className={`w-full text-left px-3 py-1.5 text-xs font-semibold transition-colors block ${
                    status === opt.value && trackedMode === opt.trackedMode
                      ? 'text-primary bg-primary/10'
                      : 'text-popover-foreground/70 hover:text-popover-foreground hover:bg-muted/40'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Discovery Timing filter */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => applyTodayOnly(!todayOnly)}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition-all border flex items-center gap-1.5 ${
              todayOnly
                ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                : 'bg-muted/30 text-muted-foreground border-border/50 hover:border-primary/40 hover:text-foreground'
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            Added Today
          </button>
        </div>

        <div className="h-4 w-px bg-border/50 shrink-0 hidden sm:block" />

        {/* Score & Review filter pills */}
        <div className="flex items-center gap-1">
          {SCORE_FILTER_OPTIONS.map((opt) => {
            const isActive = opt.value === 'sparse' 
              ? isSparse === true 
              : (minScore === opt.value && isSparse !== true)
            const isSparsePill = opt.value === 'sparse'
            
            const pill = (
              <button
                key={opt.value}
                onClick={() => applyMinScore(opt.value)}
                className={`px-3 py-1 rounded-full text-xs font-semibold transition-all border flex items-center justify-center ${
                  isActive
                    ? isSparsePill
                      ? 'bg-amber-500 text-white border-amber-500 shadow-sm'
                      : 'bg-primary text-primary-foreground border-primary shadow-sm'
                    : isSparsePill
                    ? 'bg-muted/30 text-muted-foreground border-border/50 hover:border-amber-500/40 hover:text-amber-600'
                    : 'bg-muted/30 text-muted-foreground border-border/50 hover:border-primary/40 hover:text-foreground'
                }`}
              >
                {isSparsePill ? <HelpCircle className="h-3.5 w-3.5" /> : opt.label}
              </button>
            )

            if (isSparsePill) {
              return (
                <TooltipProvider key={opt.value}>
                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <button
                          onClick={() => applyMinScore(opt.value)}
                          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all border flex items-center justify-center ${
                            isActive
                              ? 'bg-amber-500 text-white border-amber-500 shadow-sm'
                              : 'bg-muted/30 text-muted-foreground border-border/50 hover:border-amber-500/40 hover:text-amber-600'
                          }`}
                        />
                      }
                    >
                      <HelpCircle className="h-3.5 w-3.5" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Filter for sparse postings needing manual review</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )
            }
            
            return pill
          })}
        </div>

        <div className="h-4 w-px bg-border/50 shrink-0 hidden sm:block" />

        {/* Sort pills */}
        <div className="flex items-center gap-1.5 ml-auto">
          <span className="text-xs text-muted-foreground hidden lg:inline">Sort:</span>
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => applySort(opt.value)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all border ${
                sort === opt.value
                  ? 'bg-primary/10 text-primary border-primary/30'
                  : 'bg-transparent text-muted-foreground border-transparent hover:text-foreground'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 -mr-2">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="animate-pulse">Loading job board...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-4 text-center opacity-70">
            <SearchX className="h-12 w-12 text-muted-foreground" />
            <div className="space-y-1">
              <h2 className="text-xl font-medium">No jobs match these filters</h2>
              <p className="text-sm text-muted-foreground">Try clearing the filters or running a pipeline scan.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            <div className="space-y-2">
              {jobs.map((job) => (
                <JobListItem key={job.id} job={job} boardHref={boardHref} />
              ))}
            </div>

            {pages > 1 && (
              <div className="flex flex-col items-center gap-3 border-t border-border/50 py-6">
                <div className="flex flex-wrap items-center justify-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fetchJobs(buildNextState(1))}
                    disabled={page === 1 || loading}
                    className="px-2.5"
                    aria-label="Go to first page"
                  >
                    <ChevronsLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fetchJobs(buildNextState(page - 1))}
                    disabled={page === 1 || loading}
                    className="gap-2"
                  >
                    <ChevronLeft className="h-4 w-4" /> Previous
                  </Button>
                  <span className="min-w-28 text-center text-sm font-medium text-muted-foreground">
                    Page {page} of {pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fetchJobs(buildNextState(page + 1))}
                    disabled={page === pages || loading}
                    className="gap-2"
                  >
                    Next <ChevronRight className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fetchJobs(buildNextState(pages))}
                    disabled={page === pages || loading}
                    className="px-2.5"
                    aria-label="Go to last page"
                  >
                    <ChevronsRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <ImportJobDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        destination="board"
        onImported={async (jobId) => {
          if (!jobId) {
            await fetchJobs(boardStateRef.current)
            return
          }

          router.push(`/jobs/detail?id=${jobId}&from=${encodeURIComponent(boardHref)}`)
        }}
      />
    </div>
  )
}
