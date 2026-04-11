'use client'

import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/types'
import { getMatchQualityLabel } from '@/lib/utils/score'
import { ScoreRing } from '@/components/score/ScoreRing'
import { ScoreBar } from '@/components/score/ScoreBar'
import { PriorityBadge } from '@/components/score/PriorityBadge'
import { FitCategoryBadge } from '@/components/score/FitCategoryBadge'
import { MatchTierBadge } from '@/components/score/MatchTierBadge'
import { formatDate, getPlatformName } from '@/lib/utils/format'
import { getCompanyQualitySignalLabel } from '@/lib/company-quality'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { JobDescription } from '@/components/jobs/JobDescription'
import { cn } from '@/lib/utils'
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  RotateCcw,
  MapPin,
  Building2,
  Calendar,
  AlertTriangle,
  Loader2,
  Banknote,
  HelpCircle,
  Sparkles,
  ExternalLink,
} from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

type JobDetailResponse = components["schemas"]["JobDetailResponse"]
type JobStatus = components["schemas"]["StatusUpdate"]["status"]

interface JobDetailViewProps {
  jobId: number | null
  boardHref?: string
  mode?: 'page' | 'sheet'
  onClose?: () => void
}

export function JobDetailView({
  jobId,
  boardHref = '/jobs',
  mode = 'page',
  onClose,
}: JobDetailViewProps) {
  const router = useRouter()
  const isSheet = mode === 'sheet'

  const [job, setJob] = useState<JobDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rescoreRunId, setRescoreRunId] = useState<string | null>(null)

  const goBackToBoard = useCallback(() => {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back()
      return
    }

    router.push(boardHref)
  }, [boardHref, router])

  const fetchJob = useCallback(async () => {
    if (!jobId) {
      setError('No job ID provided')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const { data, error: apiError } = await api.GET('/api/jobs/{job_id}', {
        params: {
          path: { job_id: jobId },
        },
      })

      if (apiError) throw new Error('Failed to load job details')
      setJob(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [jobId])

  const updateStatus = async (newStatus: JobStatus) => {
    if (!jobId) return

    setUpdating(true)
    try {
      const { error: patchError } = await api.PATCH('/api/jobs/{job_id}/status', {
        params: {
          path: { job_id: jobId },
        },
        body: { status: newStatus },
      })
      if (patchError) throw new Error('Failed to update status')

      setJob((prev) => prev ? { ...prev, status: newStatus } : prev)
      router.refresh()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setUpdating(false)
    }
  }

  const handleRescore = async () => {
    if (!jobId || rescoreRunId) return

    try {
      const { data, error: apiError } = await api.POST('/api/jobs/{job_id}/rescore', {
        params: {
          path: { job_id: jobId },
        },
      })
      if (apiError) throw new Error('Failed to start rescoring')
      if (data) {
        setRescoreRunId(data.run_id)
      }
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  useEffect(() => {
    if (!rescoreRunId) return

    const interval = setInterval(async () => {
      try {
        const { data, error: statusError } = await api.GET('/api/pipeline/status/{run_id}', {
          params: { path: { run_id: rescoreRunId } },
        })

        if (statusError) throw statusError

        if (data.status === 'done') {
          clearInterval(interval)
          setRescoreRunId(null)
          fetchJob()
          toast.success('Job assessment refreshed')
        } else if (data.status === 'error') {
          clearInterval(interval)
          setRescoreRunId(null)
          toast.error('Rescoring failed')
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [fetchJob, rescoreRunId])

  useEffect(() => {
    fetchJob()
  }, [fetchJob])

  const shellClassName = isSheet
    ? 'mx-auto max-w-7xl space-y-8 px-5 py-5 sm:px-6 sm:py-6'
    : 'mx-auto max-w-7xl animate-in space-y-8 px-4 py-6 fade-in duration-700 sm:space-y-10 sm:px-6 sm:py-10'

  const loadingClassName = isSheet
    ? 'flex min-h-[40vh] flex-col items-center justify-center gap-4'
    : 'flex h-screen flex-col items-center justify-center gap-4'

  if (loading) {
    return (
      <div className={loadingClassName}>
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground animate-pulse">Consulting the radar matching engine...</p>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className={cn(loadingClassName, 'px-6 text-center')}>
        <h1 className="text-2xl font-bold">Job Not Found</h1>
        <p className="text-muted-foreground">{error || "The requested job doesn't exist or has been removed."}</p>
        {onClose ? (
          <Button variant="outline" className="gap-2" onClick={onClose}>
            <ArrowLeft className="h-4 w-4" /> Back to Job Board
          </Button>
        ) : (
          <Button variant="outline" className="gap-2" onClick={goBackToBoard}>
            <ArrowLeft className="h-4 w-4" /> Back to Board
          </Button>
        )}
      </div>
    )
  }

  const dimensions = job.score_breakdown?.dimensions || {}
  const fitCategory = job.score_breakdown?.fit_category as string | undefined
  const keyMatches = job.score_breakdown?.key_matches ?? []
  const redFlags = job.score_breakdown?.red_flags ?? []
  const companySignals = Array.isArray(job.company_quality_signals) ? job.company_quality_signals : []
  const matchQualityLabel = job.is_sparse ? 'Manual Review Required' : getMatchQualityLabel(job.score_breakdown?.apply_priority)
  const scoreReasoning = job.score_reasoning || 'No detailed reasoning provided.'

  return (
    <div className={shellClassName}>
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {onClose ? (
          <Button variant="ghost" className="gap-2 -ml-2 self-start px-2 text-muted-foreground hover:text-foreground" onClick={onClose}>
            <ArrowLeft className="h-4 w-4" /> Back to Job Board
          </Button>
        ) : (
          <Button
            variant="ghost"
            className="gap-2 -ml-2 self-start px-2 text-muted-foreground hover:text-foreground"
            onClick={goBackToBoard}
          >
            <ArrowLeft className="h-4 w-4" /> Back to Job Board
          </Button>
        )}
        <div className="flex w-full items-center gap-3 sm:w-auto">
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: 'outline' }), 'w-full justify-center gap-2 sm:w-auto')}
          >
            Open in ATS <ExternalLink className="h-4 w-4" />
          </a>
        </div>
      </header>

      <section className="flex flex-col items-start gap-6 lg:flex-row lg:gap-10">
        <div className="flex-1 space-y-6">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="secondary" className="uppercase tracking-widest text-[10px] py-1 px-3 bg-primary/10 text-primary border-none">
                {getPlatformName(job.ats_platform)}
              </Badge>
              {!job.is_sparse && <PriorityBadge priority={job.score_breakdown?.apply_priority} />}
              {job.status !== 'dismissed' && <FitCategoryBadge fitCategory={fitCategory} />}
              <Badge variant="outline" className="capitalize px-3 border-border/50 bg-muted/20">
                Status: {job.status}
              </Badge>
              {job.match_tier && <MatchTierBadge matchTier={job.match_tier} />}
              {job.status === 'dismissed' && job.dismissal_reason && (
                <Badge variant="destructive" className="px-3 border-none bg-destructive/15 text-destructive font-bold">
                  Reason: {job.dismissal_reason}
                </Badge>
              )}
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl lg:text-5xl xl:text-6xl">
              {job.title}
            </h1>
            <div className="grid grid-cols-1 gap-3 text-sm font-medium text-muted-foreground sm:grid-cols-2 xl:grid-cols-4 xl:gap-6">
              <div className="flex min-w-0 items-center gap-2">
                <Building2 className="h-4 w-4 shrink-0 text-primary/70" />
                <span className="truncate">{job.company_name}</span>
              </div>
              <div className="flex min-w-0 items-center gap-2">
                <Banknote className="h-4 w-4 text-green-600 dark:text-green-400 opacity-80" />
                <span className="truncate font-semibold text-foreground/80">{job.salary || 'Salary Undisclosed'}</span>
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
                <div className="relative group mt-1 shrink-0 cursor-help" title={job.is_sparse ? 'Manual Review Required' : 'Overall Fit Score'}>
                  <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl scale-75 opacity-0 transition-opacity group-hover:opacity-100" />
                  {job.is_sparse ? (
                    <div className="flex h-[72px] w-[72px] items-center justify-center rounded-full border-2 border-amber-500/20 bg-amber-500/10 text-amber-500 shadow-inner">
                      <HelpCircle className="h-8 w-8 stroke-[2]" />
                    </div>
                  ) : (
                    <ScoreRing score={job.fit_score ?? null} size={72} strokeWidth={7} />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-col items-start gap-2">
                    <h2 className="text-xl font-bold tracking-tight">
                      Match Quality:
                      <span className="block capitalize text-primary">
                        {matchQualityLabel}
                      </span>
                    </h2>
                    <Tooltip>
                      <TooltipTrigger
                        render={(triggerProps) => (
                          <Button
                            {...triggerProps}
                            variant="outline"
                            size="sm"
                            disabled={!!rescoreRunId}
                            onClick={handleRescore}
                            className="h-8 shrink-0 self-start gap-2 rounded-full border-primary/20 px-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground shadow-sm transition-all hover:border-primary/40 hover:bg-primary/5 hover:text-primary disabled:opacity-70"
                          >
                            {rescoreRunId ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Rescoring...
                              </>
                            ) : (
                              <>
                                <RotateCcw className="h-3.5 w-3.5 transition-transform duration-500 group-hover:rotate-180" />
                                Rescore
                              </>
                            )}
                          </Button>
                        )}
                      />
                      <TooltipContent className="border border-border/50 bg-popover/80 text-[10px] text-popover-foreground shadow-xl backdrop-blur-md">
                        <p>Rerun AI intelligence pass for this job</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>
              </div>
              <p className="max-w-none border-l-2 border-primary/30 pl-4 text-sm italic leading-relaxed text-muted-foreground">
                {scoreReasoning}
              </p>
            </div>

            <div className="hidden items-center gap-6 lg:flex">
              <div className="relative group cursor-help" title={job.is_sparse ? 'Manual Review Required' : 'Overall Fit Score'}>
                <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl scale-75 opacity-0 transition-opacity group-hover:opacity-100" />
                {job.is_sparse ? (
                  <div className="flex h-[110px] w-[110px] items-center justify-center rounded-full border-2 border-amber-500/20 bg-amber-500/10 text-amber-500 shadow-inner">
                    <HelpCircle className="h-12 w-12 stroke-[2]" />
                  </div>
                ) : (
                  <ScoreRing score={job.fit_score ?? null} size={110} strokeWidth={9} />
                )}
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold tracking-tight">
                    Match Quality: <span className="text-primary capitalize">{matchQualityLabel}</span>
                  </h2>
                  <Tooltip>
                    <TooltipTrigger
                      render={(triggerProps) => (
                        <Button
                          {...triggerProps}
                          variant="outline"
                          size="sm"
                          disabled={!!rescoreRunId}
                          onClick={handleRescore}
                          className="h-8 gap-2 rounded-full border-primary/20 px-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground shadow-sm transition-all hover:border-primary/40 hover:bg-primary/5 hover:text-primary disabled:opacity-70"
                        >
                          {rescoreRunId ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              Rescoring...
                            </>
                          ) : (
                            <>
                              <RotateCcw className="h-3.5 w-3.5 transition-transform duration-500 group-hover:rotate-180" />
                              Rescore
                            </>
                          )}
                        </Button>
                      )}
                    />
                    <TooltipContent className="border border-border/50 bg-popover/80 text-[10px] text-popover-foreground shadow-xl backdrop-blur-md">
                      <p>Rerun AI intelligence pass for this job</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <p className="max-w-xl border-l-2 border-primary/30 pl-4 italic leading-relaxed text-muted-foreground">
                  {scoreReasoning}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="w-full lg:w-80 shrink-0 space-y-4">
          <Card className="border-border/50 bg-card/60 backdrop-blur-xl shadow-2xl overflow-hidden">
            <CardContent className="p-5 space-y-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground pb-1">Manage Status</p>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(buttonVariants({ variant: 'default' }), 'w-full gap-2 font-bold h-11 bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20')}
              >
                Apply Now <ExternalLink className="h-4 w-4" />
              </a>
              <Button
                variant="outline"
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
            </CardContent>
          </Card>

          {!job.is_sparse && Object.keys(dimensions).length > 0 && (
            <Card className="border-border/50 bg-card/60 backdrop-blur-xl shadow-xl overflow-hidden">
              <CardContent className="p-5 space-y-4">
                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Dimension Breakdown</p>
                <div className="space-y-4">
                  {Object.entries(dimensions).map(([key, val]: [string, any]) => (
                    <ScoreBar key={key} label={key} score={typeof val === 'number' ? val : 0} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-8 pb-12 lg:grid-cols-3 lg:gap-10 lg:pb-16">
        <div className="lg:col-span-2 space-y-8">
          <div className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight underline decoration-primary/30 decoration-4 underline-offset-8">Job Description</h2>
            <JobDescription content={job.description ?? undefined} isSparse={job.is_sparse} />
            <div className="flex flex-col items-stretch gap-2 pt-2 sm:items-center">
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(buttonVariants({ variant: 'outline' }), 'h-12 w-full justify-center gap-2 rounded-2xl border-primary/20 px-8 transition-all hover:border-primary/40 hover:bg-primary/5 sm:w-auto')}
              >
                View Original Posting on {getPlatformName(job.ats_platform)} <ExternalLink className="h-4 w-4" />
              </a>
              {job.ats_platform === 'remotive' && (
                <p className="mt-2 text-center text-[10px] text-muted-foreground opacity-60">
                  Source: {getPlatformName(job.ats_platform)}
                </p>
              )}
              {job.ats_platform === 'remoteok' && (
                <div className="mt-4 flex flex-col items-center gap-1">
                  <p className="text-[10px] text-muted-foreground opacity-60">
                    Jobs provided by
                  </p>
                  <a
                    href="https://remoteok.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs font-bold text-primary hover:underline"
                  >
                    Remote OK <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
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

          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2 text-green-500">
              <CheckCircle2 className="h-4 w-4" />
              Key Matches
            </h3>
            <div className="space-y-2">
              {keyMatches.length > 0
                ? keyMatches.map((match: string) => (
                    <div key={match} className="flex gap-3 p-3 rounded-xl bg-green-500/5 border border-green-500/10 text-green-600 dark:text-green-400 text-sm">
                      <div className="flex-shrink-0 mt-0.5">
                        <CheckCircle2 className="h-4 w-4 text-green-500/70" />
                      </div>
                      <span>{match}</span>
                    </div>
                  ))
                : <span className="text-xs text-muted-foreground italic pl-3">No key matches identified.</span>}
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-4 w-4" />
              Potential Red Flags
            </h3>
            <div className="space-y-2">
              {redFlags.length > 0
                ? redFlags.map((flag: string) => (
                    <div key={flag} className="flex gap-3 p-3 rounded-xl bg-destructive/5 border border-destructive/10 text-destructive text-sm">
                      <div className="flex-shrink-0 mt-0.5">•</div>
                      <span>{flag}</span>
                    </div>
                  ))
                : <span className="text-xs text-muted-foreground italic pl-3">Clean scan: No immediate red flags detected.</span>}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
