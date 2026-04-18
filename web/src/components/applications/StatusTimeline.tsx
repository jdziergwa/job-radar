'use client'

import type { components } from '@/lib/api/types'
import { Badge } from '@/components/ui/badge'
import { formatDate } from '@/lib/utils/format'

type ApplicationEventResponse = components['schemas']['ApplicationEventResponse']

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

export function StatusTimeline({
  events,
  loading = false,
}: {
  events: ApplicationEventResponse[]
  loading?: boolean
}) {
  if (loading) {
    return (
      <div className="space-y-2.5">
        {[1, 2].map((row) => (
          <div key={row} className="h-14 animate-pulse rounded-2xl bg-muted/25" />
        ))}
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-border/40 bg-background/35 px-4 py-4 text-sm text-muted-foreground">
        No tracker history yet.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {events.map((event, index) => {
        const meta = STATUS_META[event.status] ?? {
          label: event.status.replaceAll('_', ' '),
          badge: 'border-primary/20 bg-primary/10 text-primary',
          dot: 'bg-primary',
        }
        const isLast = index === events.length - 1

        return (
          <div key={event.id} className="relative pl-7">
            {!isLast && (
              <div className="absolute left-[9px] top-5 h-[calc(100%+0.5rem)] w-px bg-border/60" />
            )}
            <span className={`absolute left-0 top-1.5 h-5 w-5 rounded-full border-[3px] border-background shadow-sm ${meta.dot}`} />
            <div className="rounded-2xl border border-border/40 bg-background/40 px-3.5 py-2.5 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest ${meta.badge}`}>
                  {meta.label}
                </Badge>
                <span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span>
              </div>
              {event.note && (
                <p className="mt-1.5 text-sm leading-relaxed text-foreground/85">{event.note}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
