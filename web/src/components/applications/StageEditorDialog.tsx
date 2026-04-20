'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  APPLICATION_STAGE_OPTIONS,
  getApplicationEventDate,
  getApplicationStageLabel,
  getTodayDateInputValue,
  normalizeTrackerDateForInput,
  type ApplicationEventResponse,
  type ApplicationStatus,
} from '@/lib/applications/stages'
import { Loader2, PencilLine, Plus } from 'lucide-react'

type StageEditorMode = 'create' | 'edit'

type StageEditorDraft = {
  canonical_phase: ApplicationStatus
  stage_label: string
  occurred_at: string
  note: string
}

function buildCreateDraft(defaultPhase: ApplicationStatus): StageEditorDraft {
  return {
    canonical_phase: defaultPhase,
    stage_label: getApplicationStageLabel(defaultPhase),
    occurred_at: getTodayDateInputValue(),
    note: '',
  }
}

function buildEditDraft(event: ApplicationEventResponse): StageEditorDraft {
  return {
    canonical_phase: event.canonical_phase,
    stage_label: event.stage_label,
    occurred_at: normalizeTrackerDateForInput(getApplicationEventDate(event)),
    note: event.note ?? '',
  }
}

export function StageEditorDialog({
  open,
  onOpenChange,
  mode,
  saving = false,
  event,
  defaultPhase,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: StageEditorMode
  saving?: boolean
  event?: ApplicationEventResponse | null
  defaultPhase: ApplicationStatus
  onSubmit: (payload: { canonical_phase: ApplicationStatus; stage_label: string; occurred_at: string; note: string | null }) => Promise<void> | void
}) {
  const initialDraft = useMemo<StageEditorDraft>(() => {
    if (mode === 'edit' && event) {
      return buildEditDraft(event)
    }

    return buildCreateDraft(defaultPhase)
  }, [defaultPhase, event, mode])

  const [draft, setDraft] = useState<StageEditorDraft>(initialDraft)
  const [labelTouched, setLabelTouched] = useState(false)

  useEffect(() => {
    setDraft(initialDraft)
    setLabelTouched(mode === 'edit' && !!event && event.stage_label.trim() !== getApplicationStageLabel(event.canonical_phase))
  }, [event, initialDraft, mode])

  const handlePhaseChange = (value: string) => {
    const nextPhase = value as ApplicationStatus
    setDraft((previous) => {
      const currentDefaultLabel = getApplicationStageLabel(previous.canonical_phase)
      const shouldSyncLabel = !labelTouched || previous.stage_label.trim() === currentDefaultLabel

      return {
        ...previous,
        canonical_phase: nextPhase,
        stage_label: shouldSyncLabel ? getApplicationStageLabel(nextPhase) : previous.stage_label,
      }
    })
  }

  const isUnchanged = (
    draft.canonical_phase === initialDraft.canonical_phase
    && draft.stage_label.trim() === initialDraft.stage_label.trim()
    && draft.occurred_at === initialDraft.occurred_at
    && draft.note === initialDraft.note
  )

  const submit = async () => {
    const stageLabel = draft.stage_label.trim()
    if (!draft.occurred_at || !stageLabel) return

    await onSubmit({
      canonical_phase: draft.canonical_phase,
      stage_label: stageLabel,
      occurred_at: draft.occurred_at,
      note: draft.note.trim() || null,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg rounded-3xl border border-border/60 bg-popover/95 shadow-2xl backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            {mode === 'create' ? <Plus className="h-4 w-4 text-primary" /> : <PencilLine className="h-4 w-4 text-primary" />}
            {mode === 'create' ? 'Add Stage' : 'Edit Stage'}
          </DialogTitle>
          <DialogDescription>
            {mode === 'create'
              ? 'Add the next meaningful step in the process. The canonical phase drives tracker analytics, while the label keeps the timeline specific.'
              : 'Edit the canonical phase, label, date, or note for this timeline entry while keeping the tracker summary aligned.'}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="stage-editor-phase">Canonical Phase</Label>
            <Select value={draft.canonical_phase} onValueChange={(value) => value && handlePhaseChange(value)}>
              <SelectTrigger id="stage-editor-phase" className="h-12 w-full rounded-2xl border-border/50 bg-background/50 px-4">
                <SelectValue placeholder="Select phase">
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
            <Label htmlFor="stage-editor-label">Stage Label</Label>
            <Input
              id="stage-editor-label"
              value={draft.stage_label}
              onChange={(event) => {
                setLabelTouched(true)
                setDraft((previous) => ({ ...previous, stage_label: event.target.value }))
              }}
              placeholder="Technical interview, recruiter screen, salary call..."
              className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="stage-editor-date">Date</Label>
            <Input
              id="stage-editor-date"
              type="date"
              value={draft.occurred_at}
              onChange={(event) => setDraft((previous) => ({ ...previous, occurred_at: event.target.value }))}
              className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="stage-editor-note">Note</Label>
            <Textarea
              id="stage-editor-note"
              value={draft.note}
              onChange={(event) => setDraft((previous) => ({ ...previous, note: event.target.value }))}
              placeholder="Optional context for this stage..."
              className="min-h-28 rounded-2xl border-border/50 bg-background/50 resize-none"
            />
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={saving || !draft.occurred_at || !draft.stage_label.trim() || (mode === 'edit' && isUnchanged)}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : mode === 'create' ? <Plus className="mr-2 h-4 w-4" /> : <PencilLine className="mr-2 h-4 w-4" />}
            {mode === 'create' ? 'Add Stage' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
