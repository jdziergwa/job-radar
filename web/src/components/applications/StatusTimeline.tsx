'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/utils/format'
import {
  getApplicationEventDate,
  getApplicationStageLabel,
  getApplicationStageMeta,
  type ApplicationEventResponse,
} from '@/lib/applications/stages'
import { PencilLine, Trash2 } from 'lucide-react'

export function StatusTimeline({
  events,
  loading = false,
  onEditEvent,
  onDeleteEvent,
  editingEventId,
  deletingEventId,
}: {
  events: ApplicationEventResponse[]
  loading?: boolean
  onEditEvent?: (event: ApplicationEventResponse) => void
  onDeleteEvent?: (event: ApplicationEventResponse) => void
  editingEventId?: number | null
  deletingEventId?: number | null
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
        const meta = getApplicationStageMeta(event.canonical_phase || event.status)
        const canonicalLabel = getApplicationStageLabel(event.canonical_phase || event.status)
        const stageLabel = event.stage_label || canonicalLabel
        const isLast = index === events.length - 1

        return (
          <div key={event.id} className="relative pl-7">
            {!isLast && (
              <div className="absolute left-[9px] top-5 h-[calc(100%+0.5rem)] w-px bg-border/60" />
            )}
            <span className={`absolute left-0 top-1.5 h-5 w-5 rounded-full border-[3px] border-background shadow-sm ${meta.dot}`} />
            <div className="rounded-2xl border border-border/40 bg-background/40 px-3.5 py-2.5 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-foreground/90">{stageLabel}</p>
                    <Badge variant="outline" className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest ${meta.badge}`}>
                      {canonicalLabel}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{formatDate(getApplicationEventDate(event))}</span>
                  </div>
                  {stageLabel !== canonicalLabel && (
                    <p className="text-[11px] font-medium text-muted-foreground">
                      Canonical phase: {canonicalLabel}
                    </p>
                  )}
                </div>
                {(onEditEvent || onDeleteEvent) && (
                  <div className="ml-auto flex items-center gap-1">
                    {onEditEvent && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onEditEvent(event)}
                        className="rounded-full text-muted-foreground/70 hover:bg-primary/10 hover:text-primary"
                        aria-label={`Edit ${stageLabel} timeline event`}
                        disabled={editingEventId === event.id}
                      >
                        <PencilLine className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {onDeleteEvent && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onDeleteEvent(event)}
                        className="rounded-full text-muted-foreground/70 hover:bg-destructive/10 hover:text-destructive"
                        aria-label={`Delete ${stageLabel} timeline event`}
                        disabled={deletingEventId === event.id}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                )}
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
