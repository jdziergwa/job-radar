'use client'

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

export type StageEditorDraft = {
  canonical_phase: ApplicationStatus
  stage_label: string
  occurred_at: string
  note: string
}

export function buildCreateStageDraft(defaultPhase: ApplicationStatus): StageEditorDraft {
  return {
    canonical_phase: defaultPhase,
    stage_label: getApplicationStageLabel(defaultPhase),
    occurred_at: getTodayDateInputValue(),
    note: '',
  }
}

export function buildStageDraftFromEvent(event: ApplicationEventResponse): StageEditorDraft {
  return {
    canonical_phase: event.canonical_phase,
    stage_label: event.stage_label,
    occurred_at: normalizeTrackerDateForInput(getApplicationEventDate(event)),
    note: event.note ?? '',
  }
}

export function normalizeStageEditorPayload(draft: StageEditorDraft) {
  const stageLabel = draft.stage_label.trim()
  if (!draft.occurred_at || !stageLabel) return null

  return {
    canonical_phase: draft.canonical_phase,
    stage_label: stageLabel,
    occurred_at: draft.occurred_at,
    note: draft.note.trim() || null,
  }
}

export function areStageDraftsEqual(left: StageEditorDraft, right: StageEditorDraft): boolean {
  return (
    left.canonical_phase === right.canonical_phase
    && left.stage_label.trim() === right.stage_label.trim()
    && left.occurred_at === right.occurred_at
    && left.note === right.note
  )
}

export function StageEditorFields({
  draft,
  onChange,
  fieldPrefix = 'stage-editor',
}: {
  draft: StageEditorDraft
  onChange: (draft: StageEditorDraft) => void
  fieldPrefix?: string
}) {
  const handlePhaseChange = (value: string) => {
    const nextPhase = value as ApplicationStatus
    const currentDefaultLabel = getApplicationStageLabel(draft.canonical_phase)
    const nextLabel = draft.stage_label.trim() === currentDefaultLabel
      ? getApplicationStageLabel(nextPhase)
      : draft.stage_label

    onChange({
      ...draft,
      canonical_phase: nextPhase,
      stage_label: nextLabel,
    })
  }

  return (
    <div className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor={`${fieldPrefix}-phase`}>Stage Category</Label>
        <Select value={draft.canonical_phase} onValueChange={(value) => value && handlePhaseChange(value)}>
          <SelectTrigger id={`${fieldPrefix}-phase`} className="h-12 w-full rounded-2xl border-border/50 bg-background/50 px-4">
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
        <Label htmlFor={`${fieldPrefix}-label`}>Stage Label</Label>
        <Input
          id={`${fieldPrefix}-label`}
          value={draft.stage_label}
          onChange={(event) => onChange({ ...draft, stage_label: event.target.value })}
          placeholder="Technical interview, recruiter screen, salary call..."
          className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
        />
      </div>

      <div className="grid gap-2">
        <Label htmlFor={`${fieldPrefix}-date`}>Date</Label>
        <Input
          id={`${fieldPrefix}-date`}
          type="date"
          value={draft.occurred_at}
          onChange={(event) => onChange({ ...draft, occurred_at: event.target.value })}
          className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
        />
      </div>

      <div className="grid gap-2">
        <Label htmlFor={`${fieldPrefix}-note`}>Note</Label>
        <Textarea
          id={`${fieldPrefix}-note`}
          value={draft.note}
          onChange={(event) => onChange({ ...draft, note: event.target.value })}
          placeholder="Optional context for this stage..."
          className="min-h-28 rounded-2xl border-border/50 bg-background/50 resize-none"
        />
      </div>
    </div>
  )
}
