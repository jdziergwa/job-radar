'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/types'
import { HighPriorityTable } from '@/components/dashboard/HighPriorityTable'
import { DashboardPulseCard } from '@/components/dashboard/DashboardPulseCard'
import {
  LayoutDashboard,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

type DashboardStats = components['schemas']['StatsOverview'] & {
  last_pipeline_run_at?: string | null
}
type DashboardJob = components['schemas']['JobResponse']
type PipelineFunnelStats = components['schemas']['PipelineFunnelStats']

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recentJobs, setRecentJobs] = useState<DashboardJob[]>([])
  const [funnelData, setFunnelData] = useState<PipelineFunnelStats | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [statsRes, jobsRes, trendsRes] = await Promise.allSettled([
        api.GET('/api/stats'),
        api.GET('/api/jobs', {
          params: {
            query: {
              per_page: 5,
              sort: 'score',
              status: 'scored'
            }
          }
        }),
        api.GET('/api/stats/trends', {
          params: { query: { days: 7 } }
        })
      ])

      if (statsRes.status === 'fulfilled') {
        if (!statsRes.value.error && statsRes.value.data) {
          setStats(statsRes.value.data as DashboardStats)
        }
      } else {
        console.error('Failed to load dashboard stats', statsRes.reason)
      }

      if (jobsRes.status === 'fulfilled') {
        if (!jobsRes.value.error && jobsRes.value.data) {
          setRecentJobs(jobsRes.value.data.jobs)
        }
      } else {
        console.error('Failed to load recent jobs', jobsRes.reason)
      }

      if (trendsRes.status === 'fulfilled') {
        if (!trendsRes.value.error && trendsRes.value.data) {
          setFunnelData(trendsRes.value.data.pipeline_funnel)
        }
      } else {
        console.error('Failed to load trend data', trendsRes.reason)
      }
    } catch (error) {
      console.error('Failed to load dashboard data', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchData()
    
    // Listen for pipeline completion to refresh dashboard data
    const handleRefresh = () => {
      void fetchData()
    }
    window.addEventListener('pipeline-finished', handleRefresh)
    return () => window.removeEventListener('pipeline-finished', handleRefresh)
  }, [])

  return (
    <div className="flex flex-col bg-background/30 px-4 py-6 animate-in fade-in duration-700 sm:px-6 sm:py-8 xl:h-dvh xl:overflow-hidden">
      <header className="mb-6 flex flex-col items-start justify-between gap-4 md:mb-8 md:flex-row md:items-center">
        <div>
          <div className="mb-1 flex items-center gap-2">
             <LayoutDashboard className="h-5 w-5 text-primary" />
             <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 sm:text-xs">Operational Cockpit</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Dashboard Overview</h1>
          <p className="text-muted-foreground mt-1 text-sm">Your job search funnel at a glance.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchData}
          disabled={loading}
          className="gap-2 border-border/50 bg-background/50 backdrop-blur-sm shadow-sm"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Data
        </Button>
      </header>

      <div className="grid flex-1 min-h-0 grid-cols-1 gap-4 sm:gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.8fr)] xl:items-start">
        <DashboardPulseCard
          stats={stats}
          funnelData={funnelData}
          lastRunAt={stats?.last_pipeline_run_at}
          loading={loading}
        />
        <div className="min-h-0 xl:self-stretch">
          <HighPriorityTable jobs={recentJobs} loading={loading} />
        </div>
      </div>
    </div>
  )
}
