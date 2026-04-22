'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { ScoreRing } from '@/components/score/ScoreRing'
import {
  getApplicationStageLabel,
  getApplicationStageMeta,
  getStalledApplicationInfo,
  type ApplicationStatus,
} from '@/lib/applications/stages'
import { Building2, CalendarDays, ChevronRight, FileText, MapPin } from 'lucide-react'
import { formatDate } from '@/lib/utils/format'
import { formatJobLocation } from '@/lib/jobs/location'

interface ApplicationJob {
  id: number
  title: string
  company_name: string
  location: string
  workplace_type?: string | null
  raw_location?: string | null
  status: string
  application_status: string
  latest_stage_label?: string | null
  latest_activity_at?: string | null
  applied_at?: string | null
  first_screen_at?: string | null
  first_interview_at?: string | null
  next_stage_label?: string | null
  next_stage_date?: string | null
  next_stage_canonical_phase?: string | null
  next_stage_note?: string | null
  fit_score?: number | null
  source?: string | null
  notes?: string | null
  url: string
  score_breakdown?: {
    apply_priority?: string
  } | null
}

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

export function ApplicationListItem({
  job,
  avgDaysToScreen = 5,
  avgDaysToReject = 10,
  avgDaysFromScreenToInterview = 7,
}: {
  job: ApplicationJob
  avgDaysToScreen?: number | null
  avgDaysToReject?: number | null
  avgDaysFromScreenToInterview?: number | null
}) {
  const meta = getApplicationStageMeta(job.application_status)
  const canonicalLabel = getApplicationStageLabel(job.application_status)
  const latestStageLabel = job.latest_stage_label?.trim() || canonicalLabel
  const showLatestStageLabel = latestStageLabel !== canonicalLabel
  const sourceLabel = job.source === 'manual' ? 'Manual' : 'Pipeline'
  const appliedLabel = job.applied_at ? `Applied ${formatDate(job.applied_at)}` : 'Applied date unavailable'
  const nextStageLabel = job.next_stage_date ? `${job.next_stage_label || 'Next stage'} · ${formatDate(job.next_stage_date)}` : (job.next_stage_label || 'No next stage scheduled')
  const displayLocation = formatJobLocation(job)
  const hasUpcomingStage = Boolean(job.next_stage_label || job.next_stage_date)
  const stalledInfo = getStalledApplicationInfo(
    job.application_status as ApplicationStatus,
    job.latest_activity_at || job.applied_at,
    hasUpcomingStage,
  )
  const stalledLabel = stalledInfo ? `No activity for ${stalledInfo.daysWithoutActivity} days` : null

  // Health / Momentum Analysis
  const [now] = useState(() => Date.now())
  const daysSinceApplied = job.applied_at ? Math.floor((now - new Date(job.applied_at).getTime()) / 86400000) : 0
  const daysSinceScreen = job.first_screen_at ? Math.floor((now - new Date(job.first_screen_at).getTime()) / 86400000) : 0
  const daysSinceActivity = job.latest_activity_at ? Math.floor((now - new Date(job.latest_activity_at).getTime()) / 86400000) : daysSinceApplied

  let health: { color: string; tooltip: string } = {
    color: 'bg-emerald-500',
    tooltip: `Recently active: ${daysSinceActivity}d since last activity.`
  }

  // Override: If a stage is already scheduled, health is always Good
  const isScheduled = hasUpcomingStage
  const status = job.application_status
  
  if (!isScheduled) {
    if (status === 'applied' && job.applied_at) {
      const screenT = avgDaysToScreen || 5
      const rejectT = avgDaysToReject || 10
      if (daysSinceApplied > rejectT) {
        health = { color: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]', tooltip: `Likely stalled: Applied ${daysSinceApplied}d ago. Past your typical ${rejectT}d rejection window.` }
      } else if (daysSinceApplied > screenT) {
        health = { color: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]', tooltip: `Delayed: Applied ${daysSinceApplied}d ago. Past typical ${screenT}d screen window.` }
      }
    } else if (status === 'screening' && job.first_screen_at) {
      const interviewT = avgDaysFromScreenToInterview || 7
      if (daysSinceScreen > interviewT + 7) {
        health = { color: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]', tooltip: `Likely stalled: ${daysSinceScreen}d since screen. Significantly past typical ${interviewT}d follow-up.` }
      } else if (daysSinceScreen > interviewT) {
        health = { color: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]', tooltip: `Delayed: ${daysSinceScreen}d since screen. Past typical ${interviewT}d follow-up window.` }
      }
    } else if (status === 'interviewing') {
      if (daysSinceActivity > 14) {
        health = { color: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]', tooltip: `Likely stalled: No activity for ${daysSinceActivity} days. Process may have stalled.` }
      } else if (daysSinceActivity > 7) {
        health = { color: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]', tooltip: `Delayed: No activity for ${daysSinceActivity} days.` }
      }
    }
  } else {
    health.tooltip = 'Recently active: Next stage is already scheduled.'
  }

  return (
    <Link
      href={`/jobs/detail?id=${job.id}&from=${encodeURIComponent('/applications')}`}
      className="group block"
      aria-label={`Open application for ${job.title} at ${job.company_name}`}
    >
      <div className="relative overflow-hidden rounded-3xl border border-border/40 bg-card/35 p-5 shadow-sm backdrop-blur-sm transition-all duration-300 hover:border-primary/25 hover:bg-card/60 hover:shadow-xl">
        <div className="flex flex-col gap-5 lg:grid lg:grid-cols-[minmax(0,1fr)_18rem_auto] lg:items-center lg:gap-5">
          <div className="flex min-w-0 items-start gap-4">
            <div className="mt-1 flex items-center gap-3">
              {job.fit_score != null ? (
                <ScoreRing score={job.fit_score} size={56} strokeWidth={5} />
              ) : (
                <div className="flex h-14 w-14 items-center justify-center rounded-full border border-border/50 bg-background/50 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                  {sourceLabel}
                </div>
              )}
            </div>

            <div className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Badge variant="outline" className={`inline-flex cursor-help items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest transition-colors ${meta.badge}`}>
                        <span className={`block h-1.5 w-1.5 shrink-0 rounded-full ${health.color.split(' ')[0]}`} />
                        {canonicalLabel}
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      <p className="text-[11px]">{health.tooltip}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                {stalledInfo && (
                  <Badge variant="outline" className="border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-amber-700 dark:text-amber-300">
                    Stalled
                  </Badge>
                )}
              </div>

              <div>
                <h3 className="truncate text-2xl font-black tracking-tight text-foreground transition-colors group-hover:text-primary">
                  {job.title}
                </h3>
                <div className="mt-0.5 flex items-center gap-2 text-lg font-bold text-muted-foreground/90">
                  <Building2 className="h-4.5 w-4.5" />
                  {job.company_name}
                </div>
                {showLatestStageLabel && (
                  <p className="mt-1 text-sm font-medium text-muted-foreground">
                    Latest step: <span className="text-foreground/85">{latestStageLabel}</span>
                  </p>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <MapPin className="h-4 w-4" />
                    {displayLocation}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <CalendarDays className="h-4 w-4" />
                    {appliedLabel}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="min-w-0 lg:w-[18rem] lg:border-l lg:border-border/40 lg:pl-5">
            <div className="space-y-1.5">
              <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/65">Next Stage</div>
              <p className={`text-sm leading-relaxed ${hasUpcomingStage ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                {nextStageLabel}
              </p>
              {stalledLabel && (
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  {stalledLabel}. Consider marking it as ghosted.
                </p>
              )}
              {job.notes && (
                <div className="inline-flex items-center gap-2 pt-1 text-xs text-muted-foreground">
                  <FileText className="h-3.5 w-3.5" />
                  Notes saved
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end">
            <div className="rounded-full border border-border/50 bg-background/60 p-3 text-muted-foreground transition-all group-hover:border-primary/30 group-hover:bg-primary/5 group-hover:text-primary">
              <ChevronRight className="h-4 w-4" />
            </div>
          </div>
        </div>

        <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-r from-primary/5 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
    </Link>
  )
}
