'use client'

import React, { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/types'
import { getMatchQualityLabel } from '@/lib/utils/score'
import { ScoreRing } from '@/components/score/ScoreRing'
import { ScoreBar } from '@/components/score/ScoreBar'
import { PriorityBadge } from '@/components/score/PriorityBadge'
import { FitCategoryBadge } from '@/components/score/FitCategoryBadge'
import { formatDate } from '@/lib/utils/format'
import { getCompanyQualitySignalLabel } from '@/lib/company-quality'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { 
  ArrowLeft, 
  ExternalLink, 
  CheckCircle2, 
  XCircle, 
  RotateCcw, 
  MapPin, 
  Calendar,
  AlertTriangle,
  Loader2,
  Banknote,
  Sparkles
} from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

type JobDetailResponse = components["schemas"]["JobDetailResponse"]
type JobStatus = components["schemas"]["StatusUpdate"]["status"]

function JobDetailContent() {
  const searchParams = useSearchParams()
  const jobId = searchParams.get('id')
  const router = useRouter()
  
  const [job, setJob] = useState<JobDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchJob = async () => {
    if (!jobId) {
      setError("No job ID provided")
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const { data, error: apiError } = await api.GET('/api/jobs/{job_id}', {
        params: {
          path: { job_id: parseInt(jobId) }
        }
      })
      if (apiError) {
        throw new Error('Failed to load job details')
      }
      setJob(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const updateStatus = async (newStatus: JobStatus) => {
    if (!jobId) return
    setUpdating(true)
    try {
      const { error: patchError } = await api.PATCH('/api/jobs/{job_id}/status', {
        params: {
          path: { job_id: parseInt(jobId) }
        },
        body: { status: newStatus }
      })
      if (patchError) throw new Error('Failed to update status')
      
      // Optimistic update
      setJob((prev) => prev ? { ...prev, status: newStatus } : prev)
      router.refresh()
    } catch (err: any) {
      alert(err.message)
    } finally {
      setUpdating(false)
    }
  }

  useEffect(() => {
    fetchJob()
  }, [jobId])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground animate-pulse">Consulting the radar matching engine...</p>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="p-8 text-center space-y-4 h-screen flex flex-col justify-center items-center">
        <h1 className="text-2xl font-bold">Job Not Found</h1>
        <p className="text-muted-foreground">{error || "The requested job doesn't exist or has been removed."}</p>
        <Link href="/jobs" className={cn(buttonVariants({ variant: "outline" }), "gap-2")}>
          <ArrowLeft className="h-4 w-4" /> Back to Board
        </Link>
      </div>
    )
  }

  const dimensions = job.score_breakdown?.dimensions || {}
  const fitCategory = job.score_breakdown?.fit_category as string | undefined
  const companySignals = Array.isArray(job.company_quality_signals) ? job.company_quality_signals : []
  const matchQualityLabel = getMatchQualityLabel(job.score_breakdown?.apply_priority)
  const scoreReasoning = job.score_reasoning || "No detailed reasoning provided."

  return (
    <div className="mx-auto max-w-7xl animate-in space-y-8 px-4 py-6 fade-in duration-700 sm:space-y-10 sm:px-6 sm:py-10">
      {/* Header Navigation */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/jobs" className={cn(buttonVariants({ variant: "ghost" }), "gap-2 -ml-2 self-start px-2 text-muted-foreground hover:text-foreground")}>
          <ArrowLeft className="h-4 w-4" /> Back to Job Board
        </Link>
        <div className="flex w-full items-center gap-3 sm:w-auto">
          <a 
            href={job.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: "outline" }), "w-full justify-center gap-2 sm:w-auto")}
          >
            View Original <ExternalLink className="h-4 w-4" />
          </a>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex flex-col items-start gap-6 lg:flex-row lg:gap-10">
        <div className="flex-1 space-y-6">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <Badge variant="secondary" className="uppercase tracking-widest text-[10px] py-1 px-3 bg-primary/10 text-primary border-none">
                  {job.ats_platform}
                </Badge>
                {!job.is_sparse && <PriorityBadge priority={job.score_breakdown?.apply_priority} />}
                {job.status !== 'dismissed' && <FitCategoryBadge fitCategory={fitCategory} />}
                <Badge variant="outline" className="capitalize px-3 border-border/50 bg-muted/20">
                  Status: {job.status}
                </Badge>
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl lg:text-5xl xl:text-6xl">
              {job.title}
            </h1>
            <div className="grid grid-cols-1 gap-3 text-sm font-medium text-muted-foreground sm:grid-cols-2 xl:grid-cols-3 xl:gap-6">
              <div className="flex min-w-0 items-center gap-2 font-semibold text-green-600 dark:text-green-400">
                <Banknote className="h-4 w-4 shrink-0" />
                <span className="truncate">{job.salary || "Salary Undisclosed"}</span>
              </div>
              <div className="flex min-w-0 items-center gap-2">
                <MapPin className="h-4 w-4 shrink-0 text-primary/70" />
                <span className="truncate">{job.location}</span>
              </div>
              <div className="flex min-w-0 items-center gap-2">
                <Calendar className="h-4 w-4 shrink-0 text-primary/70" />
                <span className="truncate">First seen {formatDate(job.first_seen_at)}</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-border/50 bg-card p-4 shadow-xl shadow-primary/5 sm:p-6">
            <div className="space-y-4 lg:hidden">
              <div className="flex items-start gap-4">
                <div className="relative group mt-1 shrink-0 cursor-help" title="Overall Fit Score">
                  <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl scale-75 opacity-0 transition-opacity group-hover:opacity-100" />
                  <ScoreRing score={job.fit_score ?? null} size={72} strokeWidth={7} />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="text-xl font-bold tracking-tight">
                    Match Quality:
                    <span className="block capitalize text-primary">{matchQualityLabel}</span>
                  </h2>
                </div>
              </div>
              <p className="max-w-none border-l-2 border-primary/30 pl-4 text-sm italic leading-relaxed text-muted-foreground">
                {scoreReasoning}
              </p>
            </div>

            <div className="hidden items-center gap-6 lg:flex">
              <div className="relative group cursor-help" title="Overall Fit Score">
                <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl scale-75 opacity-0 transition-opacity group-hover:opacity-100" />
                <ScoreRing score={job.fit_score ?? null} size={110} strokeWidth={9} />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold tracking-tight">
                  Match Quality: <span className="text-primary capitalize">{matchQualityLabel}</span>
                </h2>
                <p className="max-w-xl border-l-2 border-primary/30 pl-4 italic leading-relaxed text-muted-foreground">
                  {scoreReasoning}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Action Panel */}
        <Card className="w-full lg:w-80 border-border/50 bg-card/60 backdrop-blur-xl shadow-2xl shrink-0 overflow-hidden">
          <div className="bg-primary/10 px-6 py-4 border-b border-primary/10">
            <h3 className="text-sm font-bold uppercase tracking-widest text-primary">Manage Status</h3>
          </div>
          <CardContent className="p-6 space-y-4">
            <Button 
              className="w-full gap-2 font-bold h-11" 
              onClick={() => updateStatus('applied')}
              disabled={job.status === 'applied' || updating}
            >
              <CheckCircle2 className="h-4 w-4" />
              {job.status === 'applied' ? 'Applied' : 'Mark as Applied'}
            </Button>
            <Button 
              variant="outline" 
              className="w-full gap-2 h-11 transition-colors hover:bg-destructive/10 hover:text-destructive hover:border-destructive/20" 
              onClick={() => updateStatus('dismissed')}
              disabled={job.status === 'dismissed' || updating}
            >
              <XCircle className="h-4 w-4" />
              Dismiss Job
            </Button>
            {job.status !== 'new' && job.status !== 'scored' && (
              <Button 
                variant="ghost" 
                className="w-full gap-2 text-muted-foreground h-11" 
                onClick={() => updateStatus('scored')}
                disabled={updating}
              >
                <RotateCcw className="h-3 w-3" />
                Restore to Scored
              </Button>
            )}
            
            <Separator className="bg-border/30" />
            
            <div className="space-y-4">
              <h4 className="text-[10px] font-bold uppercase text-muted-foreground tracking-widest">Dimension Breakdown</h4>
              <div className="space-y-5">
                {Object.entries(dimensions).map(([key, val]: [string, any]) => (
                  <ScoreBar key={key} label={key} score={typeof val === 'number' ? val : 0} />
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Content Grid */}
      <section className="grid grid-cols-1 gap-8 pb-16 lg:grid-cols-3 lg:gap-10 lg:pb-20">
        <div className="lg:col-span-2 space-y-8">
           <div className="space-y-4">
              <h2 className="text-2xl font-bold tracking-tight underline decoration-primary/30 underline-offset-8 decoration-4">Job Description</h2>
              <div className="prose prose-sm max-w-none whitespace-pre-wrap rounded-[1.5rem] border border-border/40 bg-card/60 p-5 leading-relaxed dark:prose-invert prose-slate sm:p-8">
                {job.description || "The original description was empty or could not be loaded."}
              </div>
           </div>
        </div>

        <div className="space-y-8">
          {companySignals.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2 text-fuchsia-500">
                <Sparkles className="h-4 w-4" />
                Explicit Company Signals
              </h3>
              <div className="flex flex-wrap gap-2">
                {companySignals.map((signal: string) => (
                  <Badge
                    key={signal}
                    variant="outline"
                    className="bg-fuchsia-500/5 text-fuchsia-600 dark:text-fuchsia-400 border border-fuchsia-500/20 px-3 py-1 font-medium"
                  >
                    {getCompanyQualitySignalLabel(signal)}
                  </Badge>
                ))}
              </div>
              {fitCategory === 'strategic_exception' && (
                <div className="rounded-2xl border border-fuchsia-500/20 bg-fuchsia-500/5 p-4 text-sm text-muted-foreground leading-relaxed">
                  This role is being kept in play as a strategic exception. It is below your default seniority target, but the matched company-quality signals justify a bounded exception.
                </div>
              )}
            </div>
          )}

          {/* Key Matches */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2 text-green-500">
               <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
               Key Matches
            </h3>
            <div className="flex flex-wrap gap-2">
              {job.score_breakdown?.key_matches?.map((match: string) => (
                <Badge key={match} variant="secondary" className="bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20 px-3 py-1 font-medium transition-transform hover:scale-105">
                  {match}
                </Badge>
              )) || <span className="text-xs text-muted-foreground italic">No key matches identified.</span>}
            </div>
          </div>

          {/* Red Flags */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2 text-destructive">
               <AlertTriangle className="h-4 w-4" />
               Potential Red Flags
            </h3>
            <div className="space-y-2">
              {job.score_breakdown?.red_flags?.map((flag: string) => (
                <div key={flag} className="flex gap-3 p-3 rounded-xl bg-destructive/5 border border-destructive/10 text-destructive text-sm">
                  <div className="flex-shrink-0 mt-0.5">•</div>
                  <span>{flag}</span>
                </div>
              )) || <span className="text-xs text-muted-foreground italic pl-3">Clean scan: No immediate red flags detected.</span>}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default function JobPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground">Preparing details...</p>
      </div>
    }>
      <JobDetailContent />
    </Suspense>
  )
}
