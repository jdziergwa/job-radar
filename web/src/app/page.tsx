'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/types'
import { MetricCard } from '@/components/stats/MetricCard'
import { HighPriorityTable } from '@/components/dashboard/HighPriorityTable'
import { PipelineFreshnessCard } from '@/components/dashboard/PipelineFreshnessCard'
import { FunnelCard } from '@/components/stats/TrendCharts'
import {
  Zap,
  FileSearch,
  CalendarDays,
  CheckCircle2,
  BarChart3,
  LayoutDashboard,
  RefreshCw
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
      const [statsRes, jobsRes, trendsRes] = await Promise.all([
        api.GET('/api/stats'),
        api.GET('/api/jobs', {
          params: {
            query: {
              limit: 5,
              sort: 'score',
              status: 'scored'
            } as never
          }
        }),
        api.GET('/api/stats/trends', {
          params: { query: { days: 7 } as never }
        })
      ])

      if (!statsRes.error && statsRes.data) setStats(statsRes.data as DashboardStats)
      if (!jobsRes.error && jobsRes.data) setRecentJobs(jobsRes.data.jobs)
      if (!trendsRes.error && trendsRes.data) setFunnelData(trendsRes.data.pipeline_funnel)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    
    // Listen for pipeline completion to refresh dashboard data
    const handleRefresh = () => fetchData()
    window.addEventListener('pipeline-finished', handleRefresh)
    return () => window.removeEventListener('pipeline-finished', handleRefresh)
  }, [])

  return (
    <div className="flex flex-col bg-background/30 px-6 py-8 animate-in fade-in duration-700">
      <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
             <LayoutDashboard className="h-5 w-5 text-primary" />
             <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground/60">Operational Cockpit</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard Overview</h1>
          <p className="text-muted-foreground mt-1 text-sm">Your job search funnel at a glance.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchData}
          disabled={loading}
          className="gap-2 border-border/50 bg-background/50 backdrop-blur-sm"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Data
        </Button>
      </header>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            {
              title: 'New Today',
              value: stats?.new_today ?? 0,
              subtitle: `Matching today (Total discovered: ${stats?.total_new_today ?? 0})`,
              icon: Zap,
              delay: 0,
            },
            {
              title: 'This Week',
              value: stats?.new_this_week ?? 0,
              subtitle: 'New matches in last 7 days',
              icon: CalendarDays,
              delay: 75,
            },
            {
              title: 'Unscored',
              value: stats?.pending ?? 0,
              subtitle: 'Pending AI evaluation',
              icon: FileSearch,
              delay: 150,
              href: '/jobs?status=new',
            },
            {
              title: 'Applied',
              value: stats?.applied ?? 0,
              subtitle: 'Tracked applications',
              icon: CheckCircle2,
              delay: 225,
              href: '/jobs?status=applied',
            },
        ].map(({ title, value, subtitle, icon, delay, href }) => (
          <div key={title} className="animate-in fade-in slide-in-from-bottom-2 duration-500" style={{ animationDelay: `${delay}ms`, animationFillMode: 'both' }}>
            {href ? (
              <Link href={href}>
                <MetricCard title={title} value={value} subtitle={subtitle} icon={icon} loading={loading} />
              </Link>
            ) : (
              <MetricCard title={title} value={value} subtitle={subtitle} icon={icon} loading={loading} />
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content: High Priority Table + Activity Chart */}
        <div className="lg:col-span-2 space-y-6">
          <HighPriorityTable jobs={recentJobs} loading={loading} />
          {funnelData && funnelData.collected > 0 ? (
            <FunnelCard data={funnelData} />
          ) : (
            <div className="rounded-xl border border-dashed border-border/50 p-8 flex flex-col items-center justify-center text-center bg-muted/5">
               <BarChart3 className="h-8 w-8 text-muted-foreground/30 mb-2" />
               <h4 className="text-sm font-medium text-muted-foreground/60">No Funnel Data Yet</h4>
               <p className="text-xs text-muted-foreground/40 max-w-[240px]">Run the pipeline to populate search funnel counts.</p>
            </div>
          )}
        </div>

        {/* Sidebar: Pipeline Freshness */}
        <div className="space-y-6">
          <PipelineFreshnessCard
            lastRunAt={stats?.last_pipeline_run_at}
            newJobsToday={stats?.new_today ?? 0}
          />
        </div>
      </div>
    </div>
  )
}
