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
import { timeAgo, formatDate } from '@/lib/utils/format'
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
  Building2, 
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
              View Original <ExternalLink className="h-4 w-4" />
            </a>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex flex-col lg:flex-row gap-10 items-start">
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
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl text-foreground">
              {job.title}
            </h1>
            <div className="flex flex-wrap gap-6 text-muted-foreground text-sm font-medium">
              <div className="flex items-center gap-2 font-semibold text-green-600 dark:text-green-400 capitalize">
                <Banknote className="h-4 w-4" /> {job.salary || "Salary Undisclosed"}
              </div>
              <div className="flex items-center gap-2"><MapPin className="h-4 w-4 text-primary/70" /> {job.location}</div>
              <div className="flex items-center gap-2"><Calendar className="h-4 w-4 text-primary/70" /> First seen {formatDate(job.first_seen_at)}</div>
            </div>
          </div>

          <div className="flex items-center gap-6 p-6 rounded-2xl bg-card border border-border/50 shadow-xl shadow-primary/5">
            <div className="relative group cursor-help" title="Overall Fit Score">
                <div className="absolute inset-0 bg-primary/20 blur-2xl rounded-full scale-75 opacity-0 group-hover:opacity-100 transition-opacity" />
                <ScoreRing score={job.fit_score} size={110} strokeWidth={9} />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-bold tracking-tight">Match Quality: <span className="text-primary capitalize">{getMatchQualityLabel(job.score_breakdown?.apply_priority)}</span></h2>
              <p className="text-muted-foreground leading-relaxed max-w-xl italic border-l-2 border-primary/30 pl-4">
                {job.score_reasoning || "No detailed reasoning provided."}
              </p>
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
                  <ScoreBar key={key} label={key} score={val} />
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Content Grid */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-10 pb-20">
        <div className="lg:col-span-2 space-y-8">
           <div className="space-y-4">
              <h2 className="text-2xl font-bold tracking-tight underline decoration-primary/30 underline-offset-8 decoration-4">Job Description</h2>
              <div className="prose dark:prose-invert prose-slate max-w-none prose-sm leading-relaxed whitespace-pre-wrap bg-card/60 p-8 rounded-3xl border border-border/40">
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
