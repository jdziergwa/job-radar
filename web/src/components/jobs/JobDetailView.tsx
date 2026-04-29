'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/types'
import { CompleteStageDialog } from '@/components/applications/CompleteStageDialog'
import { NotesEditor } from '@/components/applications/NotesEditor'
import { AppliedResponseDialog } from '@/components/applications/AppliedResponseDialog'
import { AddStepDialog } from '@/components/applications/AddStepDialog'
import { NegativeOutcomeDialog } from '@/components/applications/NegativeOutcomeDialog'
import { ResponseMilestoneDialog } from '@/components/applications/ResponseMilestoneDialog'
import { ScheduleNextStageDialog } from '@/components/applications/ScheduleNextStageDialog'
import { StageEditorDialog } from '@/components/applications/StageEditorDialog'
import { StatusTimeline } from '@/components/applications/StatusTimeline'
import {
  getApplicationEventDate,
  getApplicationStageLabel,
  getNextApplicationStage,
  getStalledApplicationInfo,
  getTodayDateInputValue,
  normalizeTrackerDateForInput,
  APPLICATION_STAGE_TRANSITIONS,
  type ApplicationEventResponse,
  type ApplicationStatus,
} from '@/lib/applications/stages'
import { getMatchQualityLabel } from '@/lib/utils/score'
import { ScoreRing } from '@/components/score/ScoreRing'
import { ScoreBar } from '@/components/score/ScoreBar'
import { PriorityBadge } from '@/components/score/PriorityBadge'
import { FitCategoryBadge } from '@/components/score/FitCategoryBadge'
import { MatchTierBadge } from '@/components/score/MatchTierBadge'
import { formatDate, getPlatformName } from '@/lib/utils/format'
import { getCompanyQualitySignalLabel } from '@/lib/company-quality'
import { formatJobLocation } from '@/lib/jobs/location'
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
  ClipboardList,
  FileText,
  MoreHorizontal,
  PencilLine,
  Plus,
  Trash2,
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

function hasExternalJobUrl(value: string | null | undefined) {
  if (!value?.trim()) return false

  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function JobDetailView({
  jobId,
  boardHref = '/jobs',
  mode = 'page',
  onClose,
}: JobDetailViewProps) {
  const router = useRouter()
  const isSheet = mode === 'sheet'
  const backLabel = boardHref.startsWith('/applications') ? 'Back to Applications' : 'Back to Job Board'

  const [job, setJob] = useState<JobDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [timeline, setTimeline] = useState<ApplicationEventResponse[]>([])
  const [timelineLoading, setTimelineLoading] = useState(false)
  const [savingNotes, setSavingNotes] = useState(false)
  const [savingTimelineEvent, setSavingTimelineEvent] = useState(false)
  const [savingCompleteStage, setSavingCompleteStage] = useState(false)
  const [savingNextStage, setSavingNextStage] = useState(false)
  const [savingResponseMilestone, setSavingResponseMilestone] = useState(false)
  const [deletingTimelineEventId, setDeletingTimelineEventId] = useState<number | null>(null)
  const [stageEditorOpen, setStageEditorOpen] = useState(false)
  const [stageEditorMode, setStageEditorMode] = useState<'create' | 'edit'>('create')
  const [timelineEditMode, setTimelineEditMode] = useState(false)
  const [editingTimelineEvent, setEditingTimelineEvent] = useState<ApplicationEventResponse | null>(null)
  const [completeStageDialogOpen, setCompleteStageDialogOpen] = useState(false)
  const [scheduleNextStageDialogOpen, setScheduleNextStageDialogOpen] = useState(false)
  const [addStepDialogOpen, setAddStepDialogOpen] = useState(false)
  const [responseMilestoneDialogOpen, setResponseMilestoneDialogOpen] = useState(false)
  const [stageResponseDialogOpen, setStageResponseDialogOpen] = useState(false)
  const [negativeOutcomeDialogOpen, setNegativeOutcomeDialogOpen] = useState(false)
  const [prefillNextStageResponse, setPrefillNextStageResponse] = useState(false)
  const [completionSourceEvent, setCompletionSourceEvent] = useState<ApplicationEventResponse | null>(null)
  const [negativeOutcomeInitialStatus, setNegativeOutcomeInitialStatus] = useState<ApplicationStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rescoreRunId, setRescoreRunId] = useState<string | null>(null)
  const trackerMenuRef = useRef<HTMLDetailsElement | null>(null)
  const timelineScrollRef = useRef<HTMLDivElement | null>(null)
  const displayLocation = job ? formatJobLocation(job) : ''

  const goBackToBoard = useCallback(() => {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back()
      return
    }

    router.push(boardHref)
  }, [boardHref, router])

  const fetchJob = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!jobId) {
      setError('No job ID provided')
      if (!silent) setLoading(false)
      return
    }

    if (!silent) setLoading(true)
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
      if (!silent) setLoading(false)
    }
  }, [jobId])

  const fetchTimeline = useCallback(async () => {
    if (!jobId) return

    setTimelineLoading(true)
    try {
      const { data, error: apiError } = await api.GET('/api/jobs/{job_id}/timeline', {
        params: { path: { job_id: jobId } },
      })
      if (apiError) throw new Error('Failed to load tracker timeline')
      setTimeline(data?.events ?? [])
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setTimelineLoading(false)
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

  const updateApplicationStatus = async (newStatus: ApplicationStatus, note?: string, occurredAt?: string) => {
    if (!jobId) return
    const isTrackerEntry = !job?.application_status

    setUpdating(true)
    try {
      const { data, error: patchError } = await api.PATCH('/api/jobs/{job_id}/application-status', {
        params: {
          path: { job_id: jobId },
        },
        body: { application_status: newStatus, note, occurred_at: occurredAt },
      })
      if (patchError) throw new Error('Failed to update application status')

      setJob((prev) => prev ? { ...prev, ...(data ?? {}), application_status: newStatus } : prev)
      await fetchTimeline()
      router.refresh()
      toast.success(isTrackerEntry ? 'Application added to tracker' : 'Application status updated')
      return true
    } catch (err: any) {
      toast.error(err.message)
      return false
    } finally {
      setUpdating(false)
    }
  }

  const removeFromTracker = async () => {
    if (!jobId) return
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        'Delete this tracker history permanently? This will remove the timeline, notes, and reminders for this job.'
      )
      if (!confirmed) return
    }

    setUpdating(true)
    try {
      const { data, error: deleteError } = await api.DELETE('/api/jobs/{job_id}/application-status', {
        params: { path: { job_id: jobId } },
      })
      if (deleteError) throw new Error('Failed to remove job from tracker')

      setJob((prev) => prev ? {
        ...prev,
        ...(data ?? {}),
        application_status: null,
        next_stage_label: null,
        next_stage_date: null,
        next_stage_canonical_phase: null,
        next_stage_note: null,
      } : prev)
      setTimeline([])
      router.refresh()
      toast.success('Tracker history deleted')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setUpdating(false)
    }
  }

  const deleteImportedJob = async () => {
    if (!jobId || job?.source !== 'manual') return
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        'Delete this imported job permanently? This will remove the job and its application history from the database.'
      )
      if (!confirmed) return
    }

    setUpdating(true)
    try {
      const { error: deleteError } = await api.DELETE('/api/jobs/{job_id}', {
        params: { path: { job_id: jobId } },
      })
      if (deleteError) throw new Error('Failed to delete imported job')

      toast.success('Imported job deleted')
      if (isSheet && onClose) {
        onClose()
      }
      goBackToBoard()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setUpdating(false)
    }
  }

  const saveNotes = async (notes: string) => {
    if (!jobId) return

    setSavingNotes(true)
    try {
      const { data, error: patchError } = await api.PATCH('/api/jobs/{job_id}/notes', {
        params: { path: { job_id: jobId } },
        body: { notes },
      })
      if (patchError) throw new Error('Failed to save notes')

      setJob((prev) => prev ? { ...prev, ...(data ?? {}), notes } : prev)
      toast.success('Notes saved')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSavingNotes(false)
    }
  }

  const saveCompletedStage = async (payload: {
    canonical_phase: ApplicationStatus
    stage_label: string
    occurred_at: string
    note: string | null
  }) => {
    if (!jobId) return

    setSavingCompleteStage(true)
    try {
      const { error: postError } = await api.POST('/api/jobs/{job_id}/timeline', {
        params: { path: { job_id: jobId } },
        body: payload,
      })
      if (postError) throw new Error('Failed to record completed stage')

      await Promise.all([fetchTimeline(), fetchJob({ silent: true })])
      setCompleteStageDialogOpen(false)
      toast.success('Stage recorded')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSavingCompleteStage(false)
    }
  }

  const saveNextStage = async (payload: {
    canonical_phase: ApplicationStatus | null
    stage_label: string | null
    scheduled_for: string | null
    note: string | null
    mark_responded?: boolean
    response_date?: string | null
  }) => {
    if (!jobId) return

    setSavingNextStage(true)
    try {
      const { error: patchError } = await api.PATCH('/api/jobs/{job_id}/next-stage', {
        params: { path: { job_id: jobId } },
        body: payload,
      })
      if (patchError) throw new Error('Failed to save next stage')

      await Promise.all([fetchTimeline(), fetchJob({ silent: true })])
      setScheduleNextStageDialogOpen(false)
      toast.success(payload.stage_label || payload.scheduled_for ? 'Next stage saved' : 'Next stage cleared')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSavingNextStage(false)
    }
  }

  const saveResponseMilestone = async (payload: { response_date: string }) => {
    if (!jobId) return

    setSavingResponseMilestone(true)
    try {
      const { error: patchError } = await api.PATCH('/api/jobs/{job_id}/response-date', {
        params: { path: { job_id: jobId } },
        body: payload,
      })
      if (patchError) throw new Error('Failed to save response date')

      await Promise.all([fetchTimeline(), fetchJob({ silent: true })])
      setResponseMilestoneDialogOpen(false)
      toast.success('Response recorded')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSavingResponseMilestone(false)
    }
  }

  const openTimelineEventDialog = (event: ApplicationEventResponse) => {
    setStageEditorMode('edit')
    setEditingTimelineEvent(event)
    setStageEditorOpen(true)
  }

  const saveTimelineEvent = async (payload: {
    canonical_phase: ApplicationStatus
    stage_label: string
    occurred_at: string
    note: string | null
  }) => {
    if (!jobId) return

    setSavingTimelineEvent(true)
    try {
      if (stageEditorMode === 'create') {
        const { error: postError } = await api.POST('/api/jobs/{job_id}/timeline', {
          params: {
            path: { job_id: jobId },
          },
          body: payload,
        })
        if (postError) throw new Error('Failed to add timeline stage')
      } else {
        if (!editingTimelineEvent) return

        const { error: patchError } = await api.PATCH('/api/jobs/{job_id}/timeline/{event_id}', {
          params: {
            path: { job_id: jobId, event_id: editingTimelineEvent.id },
          },
          body: payload,
        })
        if (patchError) throw new Error('Failed to update timeline event')
      }

      await Promise.all([fetchTimeline(), fetchJob({ silent: true })])
      setStageEditorOpen(false)
      setEditingTimelineEvent(null)
      toast.success(stageEditorMode === 'create' ? 'Stage added to timeline' : 'Timeline stage updated')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setSavingTimelineEvent(false)
    }
  }

  const deleteTimelineEvent = async (event: ApplicationEventResponse) => {
    if (!jobId) return
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        `Delete the "${event.stage_label}" timeline stage?`
      )
      if (!confirmed) return
    }

    setDeletingTimelineEventId(event.id)
    try {
      const { error: deleteError } = await api.DELETE('/api/jobs/{job_id}/timeline/{event_id}', {
        params: {
          path: { job_id: jobId, event_id: event.id },
        },
      })
      if (deleteError) throw new Error('Failed to delete timeline event')

      await Promise.all([fetchTimeline(), fetchJob({ silent: true })])
      toast.success('Timeline stage removed')
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setDeletingTimelineEventId(null)
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
          fetchJob({ silent: true })
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

  useEffect(() => {
    if (!job?.application_status) {
      setTimeline([])
      setTimelineEditMode(false)
      return
    }

    void fetchTimeline()
  }, [fetchTimeline, job?.application_status])

  useEffect(() => {
    if (!job?.application_status || !timelineScrollRef.current) return

    const frame = window.requestAnimationFrame(() => {
      const container = timelineScrollRef.current
      if (!container) return
      container.scrollTop = container.scrollHeight
    })

    return () => window.cancelAnimationFrame(frame)
  }, [job?.application_status, timeline, timelineLoading, timelineEditMode])

  const shellClassName = isSheet
    ? 'mx-auto max-w-7xl space-y-6 px-5 py-5 sm:px-6 sm:py-6'
    : 'mx-auto max-w-7xl animate-in space-y-6 px-4 py-6 fade-in duration-700 sm:space-y-8 sm:px-6 sm:py-10'

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
            <ArrowLeft className="h-4 w-4" /> {backLabel}
          </Button>
        ) : (
          <Button variant="outline" className="gap-2" onClick={goBackToBoard}>
            <ArrowLeft className="h-4 w-4" /> {backLabel}
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
  const hasJobUrl = hasExternalJobUrl(job.url)
  const trackerStatusLabel = job.application_status ? getApplicationStageLabel(job.application_status) : null
  const trackerStatus = job.application_status as ApplicationStatus | null
  const completedTimeline = timeline.filter((event) => event.lifecycle_state !== 'scheduled')
  const completedStageTimeline = completedTimeline.filter((event) => event.event_type === 'stage')
  const scheduledTimeline = timeline.filter((event) => event.lifecycle_state === 'scheduled')
  const explicitResponseEvent = completedTimeline.find((event) => event.event_type === 'response_received') ?? null
  const nextScheduledEvent = scheduledTimeline[0] ?? null
  const nextStageDefault = trackerStatus ? getNextApplicationStage(trackerStatus) : 'screening'
  const hasNextStage = nextScheduledEvent !== null
  const upcomingStepButtonLabel = hasNextStage ? 'Edit Upcoming Step' : 'Add Upcoming Step'
  const scheduledStageToComplete = completionSourceEvent
  const completingScheduledStage = Boolean(scheduledStageToComplete)
  const latestCompletedStageEvent = completedStageTimeline[completedStageTimeline.length - 1] ?? null
  const latestCompletedTimelineEvent = completedTimeline[completedTimeline.length - 1] ?? null
  const canUseStageResponseShortcut = trackerStatus != null && ['applied', 'screening', 'interviewing', 'offer'].includes(trackerStatus)
  const shouldShowStageResponseShortcut = trackerStatus === 'applied'
    ? explicitResponseEvent === null
    : true
  const showStageRespondAction = canUseStageResponseShortcut && !hasNextStage && latestCompletedStageEvent !== null && shouldShowStageResponseShortcut
  const canCloseApplication = trackerStatus != null
    && (APPLICATION_STAGE_TRANSITIONS[trackerStatus] ?? []).some((status) =>
      ['rejected_by_company', 'rejected_by_user', 'ghosted'].includes(status)
    )
  const stalledInfo = getStalledApplicationInfo(
    trackerStatus,
    latestCompletedTimelineEvent ? getApplicationEventDate(latestCompletedTimelineEvent) : job.applied_at,
    hasNextStage,
  )
  const canMarkGhosted = stalledInfo != null
    && trackerStatus != null
    && (APPLICATION_STAGE_TRANSITIONS[trackerStatus] ?? []).includes('ghosted')

  const openCompleteStageDialog = (event?: ApplicationEventResponse | null) => {
    setCompletionSourceEvent(event ?? null)
    setCompleteStageDialogOpen(true)
  }

  const openAddStepDialog = () => {
    setAddStepDialogOpen(true)
  }

  const closeTrackerMenu = () => {
    trackerMenuRef.current?.removeAttribute('open')
  }

  return (
    <div className={shellClassName}>
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {onClose ? (
          <Button variant="ghost" className="gap-2 -ml-2 self-start px-2 text-muted-foreground hover:text-foreground" onClick={onClose}>
            <ArrowLeft className="h-4 w-4" /> {backLabel}
          </Button>
        ) : (
          <Button
            variant="ghost"
            className="gap-2 -ml-2 self-start px-2 text-muted-foreground hover:text-foreground"
            onClick={goBackToBoard}
          >
            <ArrowLeft className="h-4 w-4" /> {backLabel}
          </Button>
        )}
        {hasJobUrl && (
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
        )}
      </header>

      <section className="flex flex-col items-start gap-6 lg:flex-row lg:gap-8">
        <div className="flex-1 space-y-6">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="secondary" className="uppercase tracking-widest text-[10px] py-1 px-3 bg-primary/10 text-primary border-none">
                {getPlatformName(job.ats_platform)}
              </Badge>
              {job.source === 'manual' && (
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <Badge
                        variant="outline"
                        className="cursor-help px-3 text-[10px] font-semibold uppercase tracking-wide border-border/50 bg-muted/20 text-muted-foreground"
                      />
                    }
                  >
                    Imported
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Added manually from an external source.</p>
                  </TooltipContent>
                </Tooltip>
              )}
              {!job.is_sparse && <PriorityBadge priority={job.score_breakdown?.apply_priority} />}
              {job.status !== 'dismissed' && <FitCategoryBadge fitCategory={fitCategory} />}
              <Badge variant="outline" className="capitalize px-3 border-border/50 bg-muted/20">
                Status: {job.status}
              </Badge>
              {job.application_status && (
                <Badge variant="outline" className="px-3 border-primary/20 bg-primary/10 text-primary">
                  Tracker: {trackerStatusLabel}
                </Badge>
              )}
              {stalledInfo && (
                <Badge variant="outline" className="px-3 border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300">
                  Stalled
                </Badge>
              )}
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
                <span className="truncate">{displayLocation}</span>
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

        <div className="w-full lg:w-80 shrink-0 space-y-3">
          <Card className="border-border/50 bg-card/60 backdrop-blur-xl shadow-2xl overflow-hidden">
            <CardContent className="p-5 space-y-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground pb-1">Board Status</p>
              {hasJobUrl && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(buttonVariants({ variant: 'default' }), 'w-full gap-2 font-bold h-11 bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20')}
                >
                  Apply Now <ExternalLink className="h-4 w-4" />
                </a>
              )}
              {!job.application_status && (
                <Button
                  variant="outline"
                  className="w-full gap-2 font-bold h-11"
                  onClick={() => updateApplicationStatus('applied')}
                  disabled={updating}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Track Application
                </Button>
              )}
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
              <div className="rounded-2xl border border-border/40 bg-background/35 px-3 py-3 text-xs leading-relaxed text-muted-foreground">
                Dismissing here only hides the role from the board. If you withdrew from the interview process, use the tracker status <span className="font-semibold text-foreground/80">Withdrawn</span> instead.
              </div>
              {job.source === 'manual' && (
                <Button
                  variant="outline"
                  className="w-full gap-2 h-11 border-destructive/20 text-destructive hover:bg-destructive/10 hover:border-destructive/30"
                  onClick={deleteImportedJob}
                  disabled={updating}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete Imported Job
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

      {trackerStatus && (
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] lg:items-stretch">
          <Card className="border-border/50 bg-card/60 backdrop-blur-xl shadow-xl overflow-hidden lg:max-h-[22rem]">
            <CardContent className="flex min-h-0 flex-col px-4 pt-4 pb-2">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <ClipboardList className="h-4 w-4 text-primary" />
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Application Journey</p>
                    {stalledInfo && (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                        No activity for {stalledInfo.daysWithoutActivity} days. Consider marking this application as ghosted.
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-end">
                  <details ref={trackerMenuRef} className="group relative">
                    <summary
                      className={cn(
                        buttonVariants({ variant: 'ghost', size: 'icon-sm' }),
                        'cursor-pointer rounded-full text-muted-foreground/70 marker:hidden list-none hover:text-foreground [&::-webkit-details-marker]:hidden'
                      )}
                      aria-label="More tracker actions"
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </summary>
                    <div className="absolute right-0 top-full z-20 mt-2 min-w-[14rem] rounded-2xl border border-border/60 bg-popover/95 p-1.5 shadow-2xl backdrop-blur-xl">
                      <button
                        type="button"
                        onClick={() => {
                          closeTrackerMenu()
                          setTimelineEditMode(true)
                        }}
                        disabled={timelineLoading || timelineEditMode}
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <PencilLine className="h-3.5 w-3.5" />
                        Edit Timeline
                      </button>
                      {hasNextStage && (
                        <button
                          type="button"
                          onClick={() => {
                            closeTrackerMenu()
                            setScheduleNextStageDialogOpen(true)
                          }}
                          disabled={savingNextStage}
                          className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Calendar className="h-3.5 w-3.5" />
                          {upcomingStepButtonLabel}
                        </button>
                      )}
                      {canCloseApplication && (
                        <>
                          {canMarkGhosted && (
                            <button
                              type="button"
                              onClick={() => {
                                closeTrackerMenu()
                                setNegativeOutcomeInitialStatus('ghosted')
                                setNegativeOutcomeDialogOpen(true)
                              }}
                              disabled={updating}
                              className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              <XCircle className="h-3.5 w-3.5" />
                              Mark Ghosted
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => {
                              closeTrackerMenu()
                              setNegativeOutcomeInitialStatus(null)
                              setNegativeOutcomeDialogOpen(true)
                            }}
                            disabled={updating}
                            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                            Close Application
                          </button>
                        </>
                      )}
                      <div className="my-1 h-px bg-border/60" />
                      <button
                        type="button"
                        onClick={() => {
                          closeTrackerMenu()
                          void removeFromTracker()
                        }}
                        disabled={updating || savingCompleteStage || savingNextStage}
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-destructive transition-colors hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete Tracker History
                      </button>
                    </div>
                  </details>
                </div>
              </div>
              {timelineEditMode && (
                <div className="mt-3 flex flex-col gap-3 rounded-2xl border border-border/40 bg-background/35 px-3.5 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">Timeline Editing</p>
                    <p className="text-sm text-muted-foreground">
                      Edit existing steps, or add a completed or upcoming step.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={openAddStepDialog}
                      disabled={timelineLoading || savingTimelineEvent || savingNextStage || stageEditorOpen}
                      className="gap-2 rounded-full"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Add Step
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setTimelineEditMode(false)}
                      disabled={savingTimelineEvent || deletingTimelineEventId !== null || stageEditorOpen}
                      className="gap-2 rounded-full"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Done
                    </Button>
                  </div>
                </div>
              )}
              <div ref={timelineScrollRef} className="min-h-0 flex-1 overflow-y-auto pr-1 pt-3">
                <StatusTimeline
                  events={timeline}
                  loading={timelineLoading}
                  onCompleteScheduledEvent={timelineEditMode ? undefined : openCompleteStageDialog}
                  onMarkRespondedEvent={timelineEditMode ? undefined : () => setStageResponseDialogOpen(true)}
                  onEditEvent={timelineEditMode ? openTimelineEventDialog : undefined}
                  onEditResponseMilestone={timelineEditMode ? () => setResponseMilestoneDialogOpen(true) : undefined}
                  onDeleteEvent={timelineEditMode ? deleteTimelineEvent : undefined}
                  respondActionEventId={showStageRespondAction ? latestCompletedStageEvent?.id ?? null : null}
                  completingScheduledEventId={savingCompleteStage ? scheduledStageToComplete?.id ?? null : null}
                  respondingEventId={updating ? latestCompletedStageEvent?.id ?? null : null}
                  editingEventId={timelineEditMode && stageEditorMode === 'edit' && savingTimelineEvent ? editingTimelineEvent?.id ?? null : null}
                  editingResponseEventId={timelineEditMode && savingResponseMilestone ? explicitResponseEvent?.id ?? null : null}
                  deletingEventId={timelineEditMode ? deletingTimelineEventId : null}
                />
              </div>
            </CardContent>
          </Card>

          <div className="flex min-h-0 flex-col gap-4">
            <Card className="h-full border-border/50 bg-card/60 backdrop-blur-xl shadow-xl overflow-hidden">
              <CardContent className="flex h-full min-h-0 flex-col px-4 pt-4 pb-4">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" />
                  <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Notes</p>
                </div>
                <div className="min-h-0 flex-1 pt-3">
                  <NotesEditor
                    notes={job.notes}
                    saving={savingNotes}
                    onSave={saveNotes}
                    className="h-full"
                    textareaClassName="min-h-0"
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </section>
      )}

      <section className="grid grid-cols-1 gap-8 pb-12 lg:grid-cols-3 lg:gap-8 lg:pb-16">
        <div className="lg:col-span-2 space-y-8">
          <div className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight underline decoration-primary/30 decoration-4 underline-offset-8">Job Description</h2>
            <JobDescription content={job.description ?? undefined} isSparse={job.is_sparse} />
            <div className="flex flex-col items-stretch gap-2 pt-2 sm:items-center">
              {hasJobUrl && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(buttonVariants({ variant: 'outline' }), 'h-12 w-full justify-center gap-2 rounded-2xl border-primary/20 px-8 transition-all hover:border-primary/40 hover:bg-primary/5 sm:w-auto')}
                >
                  View Original Posting on {getPlatformName(job.ats_platform)} <ExternalLink className="h-4 w-4" />
                </a>
              )}
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

        <div className="space-y-5">
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

      <StageEditorDialog
        open={stageEditorOpen}
        onOpenChange={(open) => {
          setStageEditorOpen(open)
          if (!open) {
            setEditingTimelineEvent(null)
          }
        }}
        mode={stageEditorMode}
        saving={savingTimelineEvent}
        event={editingTimelineEvent}
        defaultPhase={nextStageDefault}
        onSubmit={saveTimelineEvent}
      />
      <CompleteStageDialog
        open={completeStageDialogOpen}
        onOpenChange={(open) => {
          setCompleteStageDialogOpen(open)
          if (!open) {
            setCompletionSourceEvent(null)
          }
        }}
        saving={savingCompleteStage}
        defaultPhase={nextStageDefault}
        initialStage={scheduledStageToComplete ? {
          canonical_phase: scheduledStageToComplete.canonical_phase,
          stage_label: scheduledStageToComplete.stage_label,
          occurred_at: normalizeTrackerDateForInput(getApplicationEventDate(scheduledStageToComplete)) || getTodayDateInputValue(),
          note: scheduledStageToComplete.note,
        } : null}
        title={completingScheduledStage ? 'Mark Completed' : 'Add Completed Step'}
        description={completingScheduledStage
          ? 'Confirm that this scheduled stage happened. Adjust the date or note if needed before saving.'
          : 'Add a completed step that already happened. This updates the current stage and adds it to the journey.'}
        submitLabel={completingScheduledStage ? 'Mark as Completed' : 'Add Completed Step'}
        onSubmit={saveCompletedStage}
      />
      <AddStepDialog
        open={addStepDialogOpen}
        onOpenChange={setAddStepDialogOpen}
        saving={savingCompleteStage || savingNextStage}
        onCompleted={() => {
          setAddStepDialogOpen(false)
          openCompleteStageDialog()
        }}
        onUpcoming={() => {
          setAddStepDialogOpen(false)
          setScheduleNextStageDialogOpen(true)
        }}
      />
      <ScheduleNextStageDialog
        open={scheduleNextStageDialogOpen}
        onOpenChange={(open) => {
          setScheduleNextStageDialogOpen(open)
          if (!open) {
            setPrefillNextStageResponse(false)
          }
        }}
        saving={savingNextStage}
        defaultPhase={nextStageDefault}
        currentStatus={trackerStatus}
        shouldPromptForResponse={trackerStatus === 'applied' && !explicitResponseEvent}
        initialMarkResponded={prefillNextStageResponse}
        initialNextStage={{
          canonical_phase: nextScheduledEvent?.canonical_phase ?? null,
          stage_label: nextScheduledEvent?.stage_label ?? null,
          scheduled_for: nextScheduledEvent?.scheduled_for ?? null,
          note: nextScheduledEvent?.note ?? null,
        }}
        onSubmit={saveNextStage}
      />
      <ResponseMilestoneDialog
        open={responseMilestoneDialogOpen}
        onOpenChange={setResponseMilestoneDialogOpen}
        saving={savingResponseMilestone}
        initialDate={explicitResponseEvent ? getApplicationEventDate(explicitResponseEvent) : null}
        onSubmit={saveResponseMilestone}
      />
      <AppliedResponseDialog
        open={stageResponseDialogOpen}
        onOpenChange={setStageResponseDialogOpen}
        saving={updating || savingNextStage}
        onPositive={() => {
          setStageResponseDialogOpen(false)
          setPrefillNextStageResponse(true)
          setScheduleNextStageDialogOpen(true)
        }}
        onNegative={() => {
          setStageResponseDialogOpen(false)
          setNegativeOutcomeInitialStatus(null)
          setNegativeOutcomeDialogOpen(true)
        }}
      />
      <NegativeOutcomeDialog
        open={negativeOutcomeDialogOpen}
        onOpenChange={(open) => {
          setNegativeOutcomeDialogOpen(open)
          if (!open) {
            setNegativeOutcomeInitialStatus(null)
          }
        }}
        saving={updating}
        currentStatus={trackerStatus}
        initialStatus={negativeOutcomeInitialStatus}
        onSubmit={async ({ status, note, occurred_at }) => {
          const ok = await updateApplicationStatus(status, note, occurred_at)
          if (ok) {
            setNegativeOutcomeDialogOpen(false)
          }
        }}
      />
    </div>
  )
}
