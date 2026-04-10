'use client'

import React, { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Sparkles, RefreshCw, AlertCircle } from 'lucide-react'

export function AIInsightsPanel() {
  const [report, setReport] = useState<string | null>(null)
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)
  const [cached, setCached] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchInsights = async (force = false) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.GET('/api/stats/insights', {
        params: { query: { days: 30, force } }
      })
      if (res.error) throw new Error('Failed to fetch insights')
      setReport(res.data.report)
      setGeneratedAt(res.data.generated_at)
      setCached(res.data.cached)
    } catch (e: any) {
      setError(e.message || 'Failed to generate insights')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInsights(false)
  }, [])

  // Format timestamp
  const formattedTime = generatedAt
    ? new Date(generatedAt.endsWith('Z') ? generatedAt : generatedAt + 'Z').toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null

  // Parse markdown to HTML
  const htmlContent = report ? (typeof window !== 'undefined' ? require('marked').marked.parse(report) : report) : ''

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm font-semibold">AI Market Insights</CardTitle>
          </div>
          {!loading && report && (
            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${cached ? 'text-muted-foreground border-border/50 bg-muted/20' : 'text-primary border-primary/30 bg-primary/10'}`}>
              {cached ? 'Cached' : 'Live'}
            </span>
          )}
        </div>
        {formattedTime && report && !loading && (
          <p className="text-[11px] text-muted-foreground/60">Generated {formattedTime}</p>
        )}
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-1/3 bg-muted/20" />
            <Skeleton className="h-3 w-full bg-muted/20" />
            <Skeleton className="h-3 w-5/6 bg-muted/20" />
            <Skeleton className="h-3 w-4/6 bg-muted/20" />
            <Skeleton className="h-4 w-1/4 mt-4 bg-muted/20" />
            <Skeleton className="h-3 w-full bg-muted/20" />
            <Skeleton className="h-3 w-3/4 bg-muted/20" />
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-dashed border-destructive/30 bg-destructive/5 p-6 sm:p-7">
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="rounded-2xl bg-destructive/10 p-3">
                <AlertCircle className="h-6 w-6 text-destructive" />
              </div>
              <div className="space-y-1.5">
                <p className="text-sm font-medium">Couldn&apos;t load AI insights</p>
                <p className="max-w-md text-xs text-muted-foreground">{error}</p>
              </div>
              <Button size="sm" onClick={() => fetchInsights(false)} variant="outline">
                Try Again
              </Button>
            </div>
          </div>
        ) : !report ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/10 p-6 sm:p-7">
            <div className="flex flex-col items-center gap-5 text-center">
              <div className="rounded-2xl bg-primary/10 p-3">
                <Sparkles className="h-6 w-6 text-primary" />
              </div>
              <div className="space-y-1.5">
                <p className="text-sm font-medium">Generate Narrative Analysis</p>
                <p className="max-w-[280px] text-xs leading-5 text-muted-foreground">
                  Analyze your last 30 days of market data with AI to uncover blockers and opportunities.
                </p>
                <p className="text-[10px] italic text-muted-foreground/50">
                  Requires one LLM API call (~$0.01).
                </p>
              </div>
              <Button size="sm" onClick={() => fetchInsights(true)} className="gap-2 px-5">
                Generate Analysis
              </Button>
            </div>
          </div>
        ) : (
          <div
            className="insights-prose"
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        )}
      </CardContent>
      {report && !loading && (
        <CardFooter className="pt-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchInsights(true)}
            disabled={loading}
            className="gap-2 text-xs border-border/50 bg-background/50"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            Regenerate With AI
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}
