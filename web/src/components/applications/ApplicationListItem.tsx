'use client'

import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { ScoreRing } from '@/components/score/ScoreRing'
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
  applied_at?: string | null
  next_step?: string | null
  next_step_date?: string | null
  fit_score?: number | null
  source?: string | null
  notes?: string | null
  url: string
  score_breakdown?: {
    apply_priority?: string
  } | null
}

const STATUS_META: Record<string, { label: string; badge: string; dot: string }> = {
  applied: {
    label: 'Applied',
    badge: 'border-sky-500/20 bg-sky-500/10 text-sky-700 dark:text-sky-300',
    dot: 'bg-sky-500',
  },
  screening: {
    label: 'Screening',
    badge: 'border-cyan-500/20 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
    dot: 'bg-cyan-500',
  },
  interviewing: {
    label: 'Interviewing',
    badge: 'border-indigo-500/20 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300',
    dot: 'bg-indigo-500',
  },
  offer: {
    label: 'Offer',
    badge: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    dot: 'bg-emerald-500',
  },
  accepted: {
    label: 'Accepted',
    badge: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    dot: 'bg-emerald-600',
  },
  rejected_by_company: {
    label: 'Rejected',
    badge: 'border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300',
    dot: 'bg-rose-500',
  },
  rejected_by_user: {
    label: 'Withdrawn',
    badge: 'border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-300',
    dot: 'bg-orange-500',
  },
  ghosted: {
    label: 'Ghosted',
    badge: 'border-slate-500/20 bg-slate-500/10 text-slate-700 dark:text-slate-300',
    dot: 'bg-slate-500',
  },
}

export function ApplicationListItem({ job }: { job: ApplicationJob }) {
  const meta = STATUS_META[job.application_status] ?? STATUS_META.applied
  const sourceLabel = job.source === 'manual' ? 'Manual' : 'Pipeline'
  const appliedLabel = job.applied_at ? `Applied ${formatDate(job.applied_at)}` : 'Applied date unavailable'
  const nextStepLabel = job.next_step_date ? `${job.next_step || 'Next step'} · ${formatDate(job.next_step_date)}` : (job.next_step || 'No upcoming steps')
  const displayLocation = formatJobLocation(job)
  const hasUpcomingStep = Boolean(job.next_step || job.next_step_date)

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
              <span className={`h-3 w-3 rounded-full shadow-sm ${meta.dot}`} />
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
                <Badge variant="outline" className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest ${meta.badge}`}>
                  {meta.label}
                </Badge>
                <Badge variant="outline" className="border-border/50 bg-background/50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/80">
                  {sourceLabel}
                </Badge>
                <Badge variant="outline" className="border-border/50 bg-background/50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/80">
                  Board: {job.status}
                </Badge>
              </div>

              <div>
                <h3 className="truncate text-xl font-black tracking-tight text-foreground transition-colors group-hover:text-primary">
                  {job.title}
                </h3>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <Building2 className="h-4 w-4" />
                    {job.company_name}
                  </span>
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
              <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/65">Next Step</div>
              <p className={`text-sm leading-relaxed ${hasUpcomingStep ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                {nextStepLabel}
              </p>
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
