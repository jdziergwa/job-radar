'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { MetricCard } from '@/components/stats/MetricCard'
import { HighPriorityTable } from '@/components/dashboard/HighPriorityTable'
import { QuickActions } from '@/components/dashboard/QuickActions'
import { ActivityChart } from '@/components/stats/TrendCharts'
import {
  Zap,
  FileSearch,
  Trash2,
  BarChart3,
  LayoutDashboard,
  RefreshCw
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null)
  const [recentJobs, setRecentJobs] = useState<any[]>([])
  const [activityData, setActivityData] = useState<any[]>([])
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
            } as any
          }
        }),
        api.GET('/api/stats/trends', {
          params: { query: { days: 7 } as any }
        })
      ])

      if (!statsRes.error) setStats(statsRes.data)
      if (!jobsRes.error) setRecentJobs((jobsRes.data as any)?.jobs || [])
      if (!trendsRes.error) setActivityData((trendsRes.data as any)?.daily_counts || [])
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

  const unscoredCount = stats?.pending ?? 0

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
            delay: 0 
          },
          { title: 'Total Unscored', value: unscoredCount, subtitle: 'Pending AI evaluation', icon: FileSearch, delay: 75 },
          { 
            title: 'Dismissed', 
            value: stats?.dismissed ?? 0, 
            subtitle: 'Not a good fit', 
            icon: Trash2, 
            delay: 150,
            href: '/jobs?status=dismissed'
          },
          { title: 'Avg Match', value: stats?.scored > 0 ? '78%' : '0%', subtitle: 'Top match avg score', icon: BarChart3, delay: 225 },
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
          {activityData.length > 0 ? (
            <ActivityChart data={activityData} />
          ) : (
            <div className="rounded-xl border border-dashed border-border/50 p-8 flex flex-col items-center justify-center text-center bg-muted/5">
               <BarChart3 className="h-8 w-8 text-muted-foreground/30 mb-2" />
               <h4 className="text-sm font-medium text-muted-foreground/60">No Activity Data Yet</h4>
               <p className="text-xs text-muted-foreground/40 max-w-[240px]">Run the pipeline to start tracking daily job discovery trends.</p>
            </div>
          )}
        </div>

        {/* Sidebar: Quick Actions & Status */}
        <div className="space-y-6">
          <QuickActions />
        </div>
      </div>
    </div>
  )
}
