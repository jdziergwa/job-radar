'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api/client'
import { ApplicationFilters, type ApplicationGroup } from '@/components/applications/ApplicationFilters'
import { ApplicationListItem } from '@/components/applications/ApplicationListItem'
import { ApplicationStats } from '@/components/applications/ApplicationStats'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ClipboardList, RefreshCw, SearchX } from 'lucide-react'

interface ApplicationJob {
  id: number
  title: string
  company_name: string
  location: string
  status: string
  application_status: string
  applied_at?: string | null
  next_step?: string | null
  next_step_date?: string | null
  fit_score?: number | null
  source?: string | null
  notes?: string | null
  url: string
  score_breakdown?: {
    apply_priority?: string
  } | null
}

interface ApplicationStatsPayload {
  total: number
  active_count: number
  offers_count: number
  response_rate: number
  avg_time_to_response_days: number | null
  source_breakdown: Record<string, number>
}

const GROUP_STATUS_MAP: Record<ApplicationGroup, string[]> = {
  active: ['applied', 'screening', 'interviewing'],
  offers: ['offer', 'accepted'],
  closed: ['rejected_by_company', 'rejected_by_user', 'ghosted'],
  all: [],
}

export default function ApplicationsPage() {
  const apiClient = api as any
  const [jobs, setJobs] = useState<ApplicationJob[]>([])
  const [stats, setStats] = useState<ApplicationStatsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [group, setGroup] = useState<ApplicationGroup>('active')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('next_step_date')
  const [searchTerm, setSearchTerm] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (searchTerm === search) return

    const timeout = window.setTimeout(() => setSearch(searchTerm), 350)
    return () => window.clearTimeout(timeout)
  }, [search, searchTerm])

  const effectiveStatus = useMemo(() => {
    if (status) return status
    const statuses = GROUP_STATUS_MAP[group]
    return statuses.length > 0 ? statuses.join(',') : ''
  }, [group, status])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const query: Record<string, string> = { sort }
      if (effectiveStatus) query.status = effectiveStatus
      if (search) query.search = search

      const [listResponse, statsResponse] = await Promise.all([
        apiClient.GET('/api/applications', { params: { query } }),
        apiClient.GET('/api/applications/stats'),
      ])

      if (listResponse.error) throw new Error('Failed to load tracked applications')
      if (statsResponse.error) throw new Error('Failed to load application stats')

      setJobs((listResponse.data?.jobs ?? []) as ApplicationJob[])
      setStats((statsResponse.data ?? null) as ApplicationStatsPayload | null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load applications')
    } finally {
      setLoading(false)
    }
  }, [apiClient, effectiveStatus, search, sort])

  useEffect(() => {
    void fetchData()
  }, [fetchData])

  useEffect(() => {
    const handleRefresh = () => void fetchData()
    window.addEventListener('pipeline-finished', handleRefresh)
    return () => window.removeEventListener('pipeline-finished', handleRefresh)
  }, [fetchData])

  return (
    <div className="flex flex-col bg-background/30 px-6 py-8 animate-in fade-in duration-700">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <ClipboardList className="h-5 w-5 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">Application Tracker</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Track Your Applications</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Monitor every application from submission to outcome, keep upcoming steps visible, and separate active processes from the broader board.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" disabled className="rounded-full border-dashed border-border/60 bg-background/50 text-muted-foreground">
            Import Job Soon
          </Button>
          <Button
            variant="outline"
            onClick={() => void fetchData()}
            disabled={loading}
            className="gap-2 rounded-full border-border/50 bg-background/50 shadow-sm"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </header>

      <ApplicationStats stats={stats} />

      <div className="mt-6">
        <ApplicationFilters
          group={group}
          status={status}
          searchTerm={searchTerm}
          sort={sort}
          onGroupChange={(value) => {
            setGroup(value)
            setStatus('')
          }}
          onStatusChange={setStatus}
          onSearchTermChange={setSearchTerm}
          onSortChange={setSort}
        />
      </div>

      <section className="mt-6 space-y-4">
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((item) => (
              <Skeleton key={item} className="h-36 rounded-3xl bg-muted/20" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-3xl border border-destructive/20 bg-destructive/5 px-6 py-8 text-center">
            <h2 className="text-lg font-bold">Applications Unavailable</h2>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex min-h-[280px] flex-col items-center justify-center gap-4 rounded-3xl border border-border/40 bg-card/25 px-6 text-center">
            <SearchX className="h-12 w-12 text-muted-foreground" />
            <div className="space-y-1">
              <h2 className="text-xl font-semibold">No tracked applications match this view</h2>
              <p className="text-sm text-muted-foreground">Try broadening the filters or move jobs into the tracker from the board.</p>
            </div>
          </div>
        ) : (
          jobs.map((job) => <ApplicationListItem key={job.id} job={job} />)
        )}
      </section>
    </div>
  )
}
