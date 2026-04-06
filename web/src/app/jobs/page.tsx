'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { JobListItem } from '@/components/jobs/JobListItem'
import { DismissalSummary } from '@/components/jobs/DismissalSummary'
import { RescoreAllButton } from '@/components/jobs/RescoreAllButton'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, Loader2, Search, SearchX, SlidersHorizontal, X, HelpCircle, ArrowUpDown, Filter } from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const STATUS_OPTIONS = [
  { value: 'new,scored,applied', label: 'Active' },
  { value: 'new', label: 'New' },
  { value: 'scored', label: 'Scored' },
  { value: 'applied', label: 'Applied' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: '', label: 'Total' },
]

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
  const [jobs, setJobs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('new,scored,applied')
  const [sort, setSort] = useState('score')
  const [minScore, setMinScore] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [search, setSearch] = useState('')
  const [isSparse, setIsSparse] = useState<boolean | null>(null)

  const fetchJobs = async (pageNum: number, opts?: { status?: string; sort?: string; minScore?: string; search?: string; is_sparse?: boolean | null }) => {
    setLoading(true)
    const s = opts?.status ?? status
    const so = opts?.sort ?? sort
    const ms = opts?.minScore ?? minScore
    const sea = opts?.hasOwnProperty('search') ? opts.search : search
    const isp = opts?.hasOwnProperty('is_sparse') ? opts.is_sparse : isSparse
    
    try {
      const query: Record<string, any> = { page: pageNum, per_page: 15, sort: so }
      if (s) query.status = s
      if (ms) query.min_score = parseInt(ms)
      if (sea) query.search = sea
      if (isp !== null) query.is_sparse = isp

      const { data } = await api.GET('/api/jobs', { params: { query } })
      if (data) {
        setJobs(data.jobs)
        setTotal(data.total)
        setPage(data.page)
        setPages(data.pages)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Check URL for initial status (e.g. from Dashboard link)
    const params = new URLSearchParams(window.location.search)
    const initialStatus = params.get('status') || 'new,scored,applied'
    
    setStatus(initialStatus)
    fetchJobs(1, { status: initialStatus })

    // Listen for pipeline completion to refresh job data
    const handleRefresh = () => fetchJobs(1, { status: 'new,scored,applied' })
    window.addEventListener('pipeline-finished', handleRefresh)
    return () => window.removeEventListener('pipeline-finished', handleRefresh)
  }, [])

  // Debounced search
  useEffect(() => {
    if (searchTerm === search) return
    
    const timer = setTimeout(() => {
      setSearch(searchTerm)
      setPage(1)
      fetchJobs(1, { search: searchTerm })
    }, 400)
    
    return () => clearTimeout(timer)
  }, [searchTerm])

  const applyStatus = (val: string) => {
    setStatus(val)
    setPage(1)
    fetchJobs(1, { status: val })
  }

  const applySort = (val: string) => {
    setSort(val)
    setPage(1)
    fetchJobs(1, { sort: val })
  }

  const applyMinScore = (val: string) => {
    if (val === 'sparse') {
      setIsSparse(true)
      setMinScore('')
      setPage(1)
      fetchJobs(1, { is_sparse: true, minScore: '' })
    } else {
      setMinScore(val)
      setIsSparse(null)
      setPage(1)
      fetchJobs(1, { minScore: val, is_sparse: null })
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
      <div className="flex flex-wrap items-center gap-3 p-4 rounded-2xl border border-border/40 bg-card/30 backdrop-blur-sm shadow-sm mb-6">
        <SlidersHorizontal className="h-4 w-4 text-muted-foreground shrink-0" />

        {/* Status filter pills */}
        <div className="flex items-center gap-1">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => applyStatus(opt.value)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all border ${
                status === opt.value
                  ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                  : 'bg-muted/30 text-muted-foreground border-border/50 hover:border-primary/40 hover:text-foreground'
              }`}
            >
              {opt.label}
            </button>
          ))}
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
            <div className="space-y-2 max-w-7xl mx-auto">
              {jobs.map((job) => (
                <JobListItem key={job.id} job={job} />
              ))}
            </div>

            {pages > 1 && (
              <div className="flex items-center justify-center gap-6 py-6 border-t border-border/50">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setPage(p => p - 1); fetchJobs(page - 1) }}
                  disabled={page === 1 || loading}
                  className="gap-2"
                >
                  <ChevronLeft className="h-4 w-4" /> Previous
                </Button>
                <span className="text-sm font-medium">Page {page} of {pages}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setPage(p => p + 1); fetchJobs(page + 1) }}
                  disabled={page === pages || loading}
                  className="gap-2"
                >
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
