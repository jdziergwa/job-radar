'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/utils/format'
import {
  getApplicationEventDate,
  getApplicationStageMeta,
  type ApplicationEventResponse,
} from '@/lib/applications/stages'
import { CheckCircle2, MailCheck, PencilLine, Trash2 } from 'lucide-react'

export function StatusTimeline({
  events,
  loading = false,
  onCompleteScheduledEvent,
  onMarkRespondedEvent,
  onEditEvent,
  onEditResponseMilestone,
  onDeleteEvent,
  respondActionEventId,
  completingScheduledEventId,
  respondingEventId,
  editingEventId,
  editingResponseEventId,
  deletingEventId,
}: {
  events: ApplicationEventResponse[]
  loading?: boolean
  onCompleteScheduledEvent?: (event: ApplicationEventResponse) => void
  onMarkRespondedEvent?: (event: ApplicationEventResponse) => void
  onEditEvent?: (event: ApplicationEventResponse) => void
  onEditResponseMilestone?: (event: ApplicationEventResponse) => void
  onDeleteEvent?: (event: ApplicationEventResponse) => void
  respondActionEventId?: number | null
  completingScheduledEventId?: number | null
  respondingEventId?: number | null
  editingEventId?: number | null
  editingResponseEventId?: number | null
  deletingEventId?: number | null
}) {
  const [expandedNotes, setExpandedNotes] = useState<Set<number>>(new Set())

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
        No journey history yet.
      </div>
    )
  }

  const completedEvents = events.filter((event) => event.lifecycle_state !== 'scheduled')
  const scheduledEvents = events.filter((event) => event.lifecycle_state === 'scheduled')

  const toggleExpandedNote = (eventId: number) => {
    setExpandedNotes((previous) => {
      const next = new Set(previous)
      if (next.has(eventId)) {
        next.delete(eventId)
      } else {
        next.add(eventId)
      }
      return next
    })
  }

  const renderEvents = (items: ApplicationEventResponse[]) => (
    <div className="space-y-3">
      {items.map((event, index) => {
        const isResponseMilestone = event.event_type === 'response_received'
        const meta = isResponseMilestone
          ? {
              label: 'Responded',
              badge: 'border-primary/20 bg-primary/10 text-primary',
              dot: 'bg-primary',
            }
          : getApplicationStageMeta(event.canonical_phase || event.status)
        const stageLabel = event.stage_label || (isResponseMilestone ? 'Response received' : '')
        const isScheduled = event.lifecycle_state === 'scheduled'
        const isLast = index === items.length - 1
        const eventDate = getApplicationEventDate(event)
        const eventDateLabel = eventDate ? formatDate(eventDate) : 'Date not set'
        const note = event.note?.trim() || ''
        const hasLongNote = note.length > 140
        const noteExpanded = expandedNotes.has(event.id)
        const showCompleteAction = Boolean(isScheduled && onCompleteScheduledEvent)
        const showRespondAction = Boolean(!isScheduled && onMarkRespondedEvent && event.id === respondActionEventId)
        const showEditAction = Boolean(onEditEvent && event.event_type === 'stage')
        const showEditResponseAction = Boolean(onEditResponseMilestone && isResponseMilestone)
        const isHighlightedUpcoming = isScheduled && index === 0
        const isHighlightedCurrent = !isScheduled && scheduledEvents.length === 0 && index === items.length - 1
        const highlightLabel = isHighlightedUpcoming ? 'Next' : isHighlightedCurrent ? 'Latest' : null

        return (
          <div key={event.id} className="relative pl-7">
            {!isLast && (
              <div className={`absolute left-[9px] top-5 h-[calc(100%+0.5rem)] w-px ${isScheduled ? 'border-l border-dashed border-border/40' : 'bg-border/60'}`} />
            )}
            <span className={`absolute left-0 top-1.5 h-5 w-5 rounded-full border-[3px] border-background shadow-sm ${meta.dot} ${isScheduled ? 'opacity-75' : ''}`} />
            <div className={`rounded-2xl border px-3.5 py-2.5 shadow-sm ${isScheduled ? 'border-border/35 bg-background/25' : 'border-border/40 bg-background/40'}`}>
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-foreground/90">{stageLabel}</p>
                    {highlightLabel && (
                      <span className="inline-flex items-center rounded-full border border-primary/15 bg-primary/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-primary">
                        {highlightLabel}
                      </span>
                    )}
                    {isScheduled && (
                      <span className="inline-flex items-center rounded-full border border-primary/15 bg-primary/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-primary">
                        Scheduled
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">{eventDateLabel}</span>
                  </div>
                </div>
                {(showCompleteAction || showRespondAction || showEditAction || showEditResponseAction || onDeleteEvent) && (
                  <div className="ml-auto flex items-center gap-1">
                    {showCompleteAction && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (onCompleteScheduledEvent) {
                            onCompleteScheduledEvent(event)
                          }
                        }}
                        className="gap-1.5 rounded-full px-2.5 text-muted-foreground/80 hover:bg-primary/10 hover:text-primary"
                        aria-label={`Mark ${stageLabel} as completed`}
                        disabled={completingScheduledEventId === event.id}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Mark Completed
                      </Button>
                    )}
                    {showRespondAction && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (onMarkRespondedEvent) {
                            onMarkRespondedEvent(event)
                          }
                        }}
                        className="gap-1.5 rounded-full px-2.5 text-muted-foreground/80 hover:bg-primary/10 hover:text-primary"
                        aria-label={`Mark ${stageLabel} as responded`}
                        disabled={respondingEventId === event.id}
                      >
                        <MailCheck className="h-3.5 w-3.5" />
                        Update Outcome
                      </Button>
                    )}
                    {showEditAction && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => {
                          if (onEditEvent) {
                            onEditEvent(event)
                          }
                        }}
                        className="rounded-full text-muted-foreground/70 hover:bg-primary/10 hover:text-primary"
                        aria-label={`Edit ${stageLabel} timeline event`}
                        disabled={editingEventId === event.id}
                      >
                        <PencilLine className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {showEditResponseAction && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => {
                          if (onEditResponseMilestone) {
                            onEditResponseMilestone(event)
                          }
                        }}
                        className="rounded-full text-muted-foreground/70 hover:bg-primary/10 hover:text-primary"
                        aria-label={`Edit ${stageLabel} response milestone`}
                        disabled={editingResponseEventId === event.id}
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
              {note && (
                <div className="mt-1.5">
                  <p className={`text-sm leading-relaxed text-foreground/85 ${hasLongNote && !noteExpanded ? 'line-clamp-2' : ''}`}>
                    {note}
                  </p>
                  {hasLongNote && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleExpandedNote(event.id)}
                      className="-ml-2 mt-1 h-auto rounded-full px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                    >
                      {noteExpanded ? 'Show Less' : 'Show More'}
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )

  return (
    <div className="space-y-3">
      {completedEvents.length > 0 && (
        <div className="space-y-3">
          {scheduledEvents.length > 0 && (
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">Completed</p>
          )}
          {renderEvents(completedEvents)}
        </div>
      )}
      {scheduledEvents.length > 0 && (
        <div className="space-y-3">
          {completedEvents.length > 0 && (
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">Upcoming</p>
          )}
          {renderEvents(scheduledEvents)}
        </div>
      )}
    </div>
  )
}
