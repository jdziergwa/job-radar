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
import { MatchTierBadge } from '@/components/score/MatchTierBadge'
import { timeAgo, formatDate, getPlatformName } from '@/lib/utils/format'
import { getCompanyQualitySignalLabel } from '@/lib/company-quality'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { JobDescription } from '@/components/jobs/JobDescription'
import { cn } from '@/lib/utils'
import { PipelineProgressDialog } from '@/components/pipeline/PipelineProgressDialog'
import {
  ArrowLeft,
  ExternalLink,
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
  Sparkles
} from 'lucide-react'
import Link from 'next/link'
import { 
  Tooltip, 
  TooltipContent, 
  TooltipProvider, 
  TooltipTrigger 
} from '@/components/ui/tooltip'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

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

  const [rescoreRunId, setRescoreRunId] = useState<string | null>(null)

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
      if (apiError) throw new Error('Failed to load job details')
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
          path: { job_id: parseInt(jobId) }
        }
      })
      if (apiError) throw new Error('Failed to start rescoring')
      if (data) {
        setRescoreRunId(data.run_id)
      }
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  // Poll for rescore status
  useEffect(() => {
    if (!rescoreRunId) return

    let interval = setInterval(async () => {
      try {
        const { data, error: statusError } = await api.GET('/api/pipeline/status/{run_id}', {
          params: { path: { run_id: rescoreRunId } }
        })

        if (statusError) throw statusError

        if (data.status === 'done') {
          clearInterval(interval)
          setRescoreRunId(null)
          fetchJob()
          toast.success("Job assessment refreshed")
        } else if (data.status === 'error') {
          clearInterval(interval)
          setRescoreRunId(null)
          toast.error("Rescoring failed")
        }
      } catch (err) {
        console.error("Polling error:", err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [rescoreRunId])

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

  return (
    <div className="max-w-7xl mx-auto px-6 py-10 space-y-10 animate-in fade-in duration-700">
      {/* Header Navigation */}
      <header className="flex justify-between items-center">
        <Link href="/jobs" className={cn(buttonVariants({ variant: "ghost" }), "gap-2 -ml-2 text-muted-foreground hover:text-foreground")}>
          <ArrowLeft className="h-4 w-4" /> Back to Job Board
        </Link>
        <div className="flex items-center gap-3">
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(buttonVariants({ variant: "outline" }), "gap-2")}
            >
              Open in ATS <ExternalLink className="h-4 w-4" />
            </a>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex flex-col lg:flex-row gap-10 items-start">
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
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl text-foreground">
              {job.title}
            </h1>
            <div className="flex flex-wrap gap-6 text-muted-foreground text-sm font-medium">
              <div className="flex items-center gap-2"><Building2 className="h-4 w-4 text-primary/70" /> {job.company_name}</div>
              <div className="flex items-center gap-2">
                <Banknote className="h-4 w-4 text-green-600 dark:text-green-400 opacity-80" /> 
                <span className="font-semibold text-foreground/80">{job.salary || "Salary Undisclosed"}</span>
              </div>
              <div className="flex items-center gap-2"><MapPin className="h-4 w-4 text-primary/70" /> {job.location}</div>
              <div className="flex items-center gap-2"><Calendar className="h-4 w-4 text-primary/70" /> First seen {formatDate(job.first_seen_at)}</div>
            </div>
          </div>

          <div className="flex items-center gap-6 p-6 rounded-2xl bg-card border border-border/50 shadow-xl shadow-primary/5">
            <div className="relative group cursor-help" title={job.is_sparse ? "Manual Review Required" : "Overall Fit Score"}>
                <div className="absolute inset-0 bg-primary/20 blur-2xl rounded-full scale-75 opacity-0 group-hover:opacity-100 transition-opacity" />
                {job.is_sparse ? (
                  <div className="w-[110px] h-[110px] rounded-full bg-amber-500/10 border-2 border-amber-500/20 flex items-center justify-center text-amber-500 shadow-inner">
                    <HelpCircle className="h-12 w-12 stroke-[2]" />
                  </div>
                ) : (
                  <ScoreRing score={job.fit_score} size={110} strokeWidth={9} />
                )}
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold tracking-tight">
                  Match Quality: <span className="text-primary capitalize">{job.is_sparse ? "Manual Review Required" : getMatchQualityLabel(job.score_breakdown?.apply_priority)}</span>
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
                            className="h-8 px-3 rounded-full border-primary/20 hover:border-primary/40 hover:bg-primary/5 text-muted-foreground hover:text-primary transition-all group gap-2 text-[10px] font-bold uppercase tracking-wider shadow-sm disabled:opacity-70"
                         >
                            {rescoreRunId ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Rescoring...
                              </>
                            ) : (
                              <>
                                <RotateCcw className="h-3.5 w-3.5 group-hover:rotate-180 transition-transform duration-500" />
                                Rescore
                              </>
                            )}
                         </Button>
                       )}
                    />
                    <TooltipContent className="text-[10px] bg-popover/80 backdrop-blur-md border border-border/50 text-popover-foreground shadow-xl">
                      <p>Rerun AI intelligence pass for this job</p>
                    </TooltipContent>
                  </Tooltip>
              </div>
              <p className="text-muted-foreground leading-relaxed max-w-xl italic border-l-2 border-primary/30 pl-4">
                {job.score_reasoning || "No detailed reasoning provided."}
              </p>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="w-full lg:w-80 shrink-0 space-y-4">
          {/* Action Panel */}
          <Card className="border-border/50 bg-card/60 backdrop-blur-xl shadow-2xl overflow-hidden">
            <CardContent className="p-5 space-y-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground pb-1">Manage Status</p>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(buttonVariants({ variant: "default" }), "w-full gap-2 font-bold h-11 bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20")}
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

          {/* Dimension Breakdown */}
          {!job.is_sparse && Object.keys(dimensions).length > 0 && (
            <Card className="border-border/50 bg-card/60 backdrop-blur-xl shadow-xl overflow-hidden">
              <CardContent className="p-5 space-y-4">
                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Dimension Breakdown</p>
                <div className="space-y-4">
                  {Object.entries(dimensions).map(([key, val]: [string, any]) => (
                    <ScoreBar key={key} label={key} score={val} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </section>

      {/* Content Grid */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-10 pb-20">
        <div className="lg:col-span-2 space-y-8">
           <div className="space-y-4">
              <h2 className="text-2xl font-bold tracking-tight underline decoration-primary/30 underline-offset-8 decoration-4">Job Description</h2>
              <JobDescription content={job.description} isSparse={job.is_sparse} />
              <div className="flex justify-center pt-4">
                   <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={cn(buttonVariants({ variant: "outline" }), "gap-2 rounded-2xl px-8 h-12 border-primary/20 hover:bg-primary/5 hover:border-primary/40 transition-all")}
                    >
                      View Original Posting on {getPlatformName(job.ats_platform)} <ExternalLink className="h-4 w-4" />
                    </a>
                    { job.ats_platform === 'remotive' && (
                      <p className="text-[10px] text-muted-foreground mt-2 text-center opacity-60">
                        Source: {getPlatformName(job.ats_platform)}
                      </p>
                    )}
                    { job.ats_platform === 'remoteok' && (
                      <div className="flex flex-col items-center gap-1 mt-4">
                        <p className="text-[10px] text-muted-foreground opacity-60">
                          Jobs provided by
                        </p>
                        <a 
                          href="https://remoteok.com" 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-xs font-bold text-primary hover:underline flex items-center gap-1"
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

          {/* Key Matches */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2 text-green-500">
               <CheckCircle2 className="h-4 w-4" />
               Key Matches
            </h3>
            <div className="space-y-2">
              {job.score_breakdown?.key_matches?.length > 0
                ? job.score_breakdown.key_matches.map((match: string) => (
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

          {/* Red Flags */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2 text-destructive">
               <AlertTriangle className="h-4 w-4" />
               Potential Red Flags
            </h3>
            <div className="space-y-2">
              {job.score_breakdown?.red_flags?.length > 0
                ? job.score_breakdown.red_flags.map((flag: string) => (
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

export default function JobDetailPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground animate-pulse">Consulting the radar matching engine...</p>
      </div>
    }>
      <JobDetailContent />
    </Suspense>
  )
}
