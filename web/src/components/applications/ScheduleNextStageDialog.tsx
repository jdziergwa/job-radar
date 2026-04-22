'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  APPLICATION_STAGE_OPTIONS,
  getApplicationStageLabel,
  getTodayDateInputValue,
  normalizeTrackerDateForInput,
  type ApplicationStatus,
} from '@/lib/applications/stages'
import { CalendarClock, Loader2, Trash2 } from 'lucide-react'

type NextStagePayload = {
  canonical_phase: ApplicationStatus | null
  stage_label: string | null
  scheduled_for: string | null
  note: string | null
  mark_responded?: boolean
  response_date?: string | null
}

type NextStageDraft = {
  canonical_phase: ApplicationStatus
  stage_label: string
  scheduled_for: string
  note: string
}

export function ScheduleNextStageDialog({
  open,
  onOpenChange,
  saving = false,
  defaultPhase,
  currentStatus,
  shouldPromptForResponse = false,
  initialMarkResponded = false,
  initialNextStage,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  saving?: boolean
  defaultPhase: ApplicationStatus
  currentStatus: ApplicationStatus | null
  shouldPromptForResponse?: boolean
  initialMarkResponded?: boolean
  initialNextStage: NextStagePayload
  onSubmit: (payload: NextStagePayload) => Promise<void> | void
}) {
  const initialDraft = useMemo<NextStageDraft>(
    () => ({
      canonical_phase: initialNextStage.canonical_phase ?? defaultPhase,
      stage_label: initialNextStage.stage_label ?? getApplicationStageLabel(initialNextStage.canonical_phase ?? defaultPhase),
      scheduled_for: normalizeTrackerDateForInput(initialNextStage.scheduled_for),
      note: initialNextStage.note ?? '',
    }),
    [defaultPhase, initialNextStage.canonical_phase, initialNextStage.stage_label, initialNextStage.scheduled_for, initialNextStage.note],
  )

  const [draft, setDraft] = useState<NextStageDraft>(initialDraft)
  const shouldSeedResponse = shouldPromptForResponse && currentStatus === 'applied'
  const [markResponded, setMarkResponded] = useState(shouldSeedResponse && initialMarkResponded)
  const [responseDate, setResponseDate] = useState(
    shouldSeedResponse && initialMarkResponded
      ? getTodayDateInputValue()
      : '',
  )

  useEffect(() => {
    setDraft(initialDraft)
    setMarkResponded(shouldSeedResponse && initialMarkResponded)
    setResponseDate(
      shouldSeedResponse && initialMarkResponded
        ? getTodayDateInputValue()
        : '',
    )
  }, [currentStatus, initialDraft, initialMarkResponded, open, shouldSeedResponse])

  const hasExistingNextStage = Boolean(initialNextStage.stage_label || initialNextStage.scheduled_for || initialNextStage.note)
  const hasChanges = (
    draft.canonical_phase !== initialDraft.canonical_phase
    || draft.stage_label.trim() !== initialDraft.stage_label.trim()
    || draft.scheduled_for !== initialDraft.scheduled_for
    || draft.note !== initialDraft.note
    || (shouldPromptForResponse && (markResponded || Boolean(responseDate)))
  )
  const canSave = Boolean(draft.stage_label.trim() || draft.scheduled_for) && (!markResponded || Boolean(responseDate))

  const handlePhaseChange = (value: string) => {
    const nextPhase = value as ApplicationStatus
    const currentDefaultLabel = getApplicationStageLabel(draft.canonical_phase)
    const nextDefaultLabel = getApplicationStageLabel(nextPhase)
    setDraft((previous) => ({
      ...previous,
      canonical_phase: nextPhase,
      stage_label: previous.stage_label.trim() === currentDefaultLabel ? nextDefaultLabel : previous.stage_label,
    }))
  }

  const submit = async () => {
    if (!canSave) return

    await onSubmit({
      canonical_phase: draft.canonical_phase,
      stage_label: draft.stage_label.trim() || null,
      scheduled_for: draft.scheduled_for || null,
      note: draft.note.trim() || null,
      mark_responded: markResponded,
      response_date: markResponded ? responseDate || null : null,
    })
  }

  const clear = async () => {
    await onSubmit({
      canonical_phase: null,
      stage_label: null,
      scheduled_for: null,
      note: null,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-w-lg min-w-0 flex-col overflow-hidden rounded-3xl border border-border/60 bg-popover/95 shadow-2xl backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <CalendarClock className="h-4 w-4 text-primary" />
            {hasExistingNextStage ? 'Edit Upcoming Step' : 'Add Upcoming Step'}
          </DialogTitle>
          <DialogDescription>
            Plan the next step so it appears in the journey before it happens.
          </DialogDescription>
        </DialogHeader>

        <div className="grid min-w-0 gap-4">
          {shouldPromptForResponse && currentStatus === 'applied' && (
            <div className="rounded-2xl border border-border/40 bg-background/30 p-4">
              <div className="flex items-start gap-3">
                <Checkbox
                  checked={markResponded}
                  onCheckedChange={(checked) => setMarkResponded(Boolean(checked))}
                  aria-label="Mark this application as responded"
                  className="mt-0.5"
                />
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-semibold text-foreground/90">Mark as responded</p>
                  <p className="text-sm text-muted-foreground">
                    Record the recruiter reply before this scheduled stage happens.
                  </p>
                </div>
              </div>
              {markResponded && (
                <div className="mt-4 grid gap-2">
                  <Label htmlFor="next-stage-response-date">Response Date</Label>
                  <Input
                    id="next-stage-response-date"
                    type="date"
                    value={responseDate}
                    onChange={(event) => setResponseDate(event.target.value)}
                    className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
                  />
                </div>
              )}
            </div>
          )}

          <div className="grid gap-2">
            <Label htmlFor="next-stage-phase">Stage Category</Label>
            <Select value={draft.canonical_phase} onValueChange={(value) => value && handlePhaseChange(value)}>
              <SelectTrigger id="next-stage-phase" className="h-12 w-full rounded-2xl border-border/50 bg-background/50 px-4">
                <SelectValue placeholder="Select stage">
                  {getApplicationStageLabel(draft.canonical_phase)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {APPLICATION_STAGE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="next-stage-label">Stage Name</Label>
            <Input
              id="next-stage-label"
              value={draft.stage_label}
              onChange={(event) => setDraft((previous) => ({ ...previous, stage_label: event.target.value }))}
              placeholder="Technical interview, take-home task, hiring manager call..."
              className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="next-stage-date">Scheduled Date</Label>
            <Input
              id="next-stage-date"
              type="date"
              value={draft.scheduled_for}
              onChange={(event) => setDraft((previous) => ({ ...previous, scheduled_for: event.target.value }))}
              className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="next-stage-note">Note</Label>
            <Textarea
              id="next-stage-note"
              value={draft.note}
              onChange={(event) => setDraft((previous) => ({ ...previous, note: event.target.value }))}
              placeholder="Optional context for this upcoming stage..."
              className="min-h-28 rounded-2xl border-border/50 bg-background/50 resize-none"
            />
          </div>
        </div>

        <DialogFooter className="flex-row items-center justify-between gap-2">
          {hasExistingNextStage ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void clear()}
              disabled={saving}
              className="gap-1.5 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
              Clear
            </Button>
          ) : (
            <div className="w-0" />
          )}
          <div className="ml-auto flex min-w-0 items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => void submit()}
              disabled={saving || !hasChanges || !canSave}
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CalendarClock className="mr-2 h-4 w-4" />}
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
