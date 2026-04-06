'use client'

import React, { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { ActivityChart, DistributionChart } from '@/components/stats/TrendCharts'
import { SkipReasonsChart, CountryChart, MissingSkillsChart, SalaryChart } from '@/components/stats/MarketCharts'
import { AIInsightsPanel } from '@/components/stats/AIInsightsPanel'
import { CompanyTable } from '@/components/stats/CompanyTable'
import { 
  BarChart3, 
  TrendingUp, 
  RefreshCw, 
  AlertCircle,
  Clock,
  Briefcase
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export default function StatsPage() {
  const [trends, setTrends] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [market, setMarket] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [trendsRes, statsRes, marketRes] = await Promise.all([
        api.GET('/api/stats/trends', {
          params: { query: { days: 30 } }
        }),
        api.GET('/api/stats'),
        api.GET('/api/stats/market', {
          params: { query: { days: 30 } }
        }),
      ])

      if (trendsRes.error) throw new Error('Failed to fetch trend data')
      if (statsRes.error) throw new Error('Failed to fetch stats overview')
      if (marketRes.error) throw new Error('Failed to fetch market data')

      setTrends(trendsRes.data)
      setStats(statsRes.data)
      setMarket(marketRes.data)
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()

    // Listen for pipeline completion to refresh analytics data
    const handleRefresh = () => fetchData()
    window.addEventListener('pipeline-finished', handleRefresh)
    return () => window.removeEventListener('pipeline-finished', handleRefresh)
  }, [])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 text-center px-4">
        <div className="bg-destructive/10 p-4 rounded-full">
          <AlertCircle className="h-10 w-10 text-destructive" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-bold">Analytics Unavailable</h2>
          <p className="text-muted-foreground text-sm max-w-sm">
            {error}. Please check your connection or try again later.
          </p>
        </div>
        <Button onClick={fetchData} variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Retry Fetch
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col bg-background/30 px-6 py-8 animate-in fade-in slide-in-from-bottom-2 duration-700">
      <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 className="h-5 w-5 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 font-mono">Market Intelligence</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Stats & Analytics</h1>
          <p className="text-muted-foreground mt-1 text-sm max-w-2xl">
            Deep insights into job discovery performance, skill trends, and organizational scoring across your tailored job search funnel.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-muted/40 px-3 py-1.5 rounded-full border border-border/50 text-[11px] font-medium text-muted-foreground">
             <Clock className="h-3 w-3" />
             Last 30 Days
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={fetchData} 
            disabled={loading}
            className="gap-2 border-border/50 bg-background/50 backdrop-blur-sm shadow-sm"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </header>

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          <Skeleton className="h-[340px] w-full rounded-xl bg-muted/20 lg:col-span-2" />
          <Skeleton className="h-[340px] w-full rounded-xl bg-muted/20" />
          <Skeleton className="h-[340px] w-full rounded-xl bg-muted/20" />
          <Skeleton className="h-[340px] w-full rounded-xl bg-muted/20" />
          <Skeleton className="h-[400px] w-full rounded-xl bg-muted/20 lg:col-span-2" />
          <Skeleton className="h-[300px] w-full rounded-xl bg-muted/20 lg:col-span-2" />
        </div>
      ) : (
        <div className="space-y-8">
          {/* Job Activity — full width */}
          <ActivityChart data={trends?.daily_counts || []} />

          {/* Market Signal Row — Skip Reasons, Countries, Missing Skills, Salaries */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <SkipReasonsChart data={market?.skip_reason_distribution || []} />
            <CountryChart data={market?.country_distribution || []} />
            <MissingSkillsChart data={market?.missing_skills || []} />
            <SalaryChart data={market?.salary_distribution || []} />
          </div>

          {/* Distribution + Company Table */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1">
              <DistributionChart data={stats?.score_distribution || {}} />
            </div>
            <div className="lg:col-span-2">
              <CompanyTable data={trends?.company_stats || []} />
            </div>
          </div>

          {/* AI Narrative Insights */}
          <div className="pb-8">
            <AIInsightsPanel />
          </div>
        </div>
      )}
    </div>
  )
}
