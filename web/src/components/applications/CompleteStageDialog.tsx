'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  buildCreateStageDraft,
  normalizeStageEditorPayload,
  StageEditorFields,
  type StageEditorDraft,
} from '@/components/applications/StageEditorFields'
import { normalizeTrackerDateForInput, type ApplicationStatus } from '@/lib/applications/stages'
import { CheckCircle2, Loader2 } from 'lucide-react'

export function CompleteStageDialog({
  open,
  onOpenChange,
  saving = false,
  defaultPhase,
  initialStage,
  title = 'Record Stage',
  description = 'Record the latest hiring stage that already happened. This updates the current stage and adds it to the journey.',
  submitLabel = 'Record Stage',
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  saving?: boolean
  defaultPhase: ApplicationStatus
  initialStage?: {
    canonical_phase: ApplicationStatus
    stage_label: string
    occurred_at: string
    note?: string | null
  } | null
  title?: string
  description?: string
  submitLabel?: string
  onSubmit: (payload: { canonical_phase: ApplicationStatus; stage_label: string; occurred_at: string; note: string | null }) => Promise<void> | void
}) {
  const initialDraft = useMemo<StageEditorDraft>(() => {
    if (initialStage) {
      return {
        canonical_phase: initialStage.canonical_phase,
        stage_label: initialStage.stage_label,
        occurred_at: normalizeTrackerDateForInput(initialStage.occurred_at),
        note: initialStage.note ?? '',
      }
    }
    return buildCreateStageDraft(defaultPhase)
  }, [defaultPhase, initialStage])
  const [draft, setDraft] = useState<StageEditorDraft>(initialDraft)

  useEffect(() => {
    setDraft(initialDraft)
  }, [initialDraft, open])

  const submit = async () => {
    const payload = normalizeStageEditorPayload(draft)
    if (!payload) return
    await onSubmit(payload)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg rounded-3xl border border-border/60 bg-popover/95 shadow-2xl backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <StageEditorFields draft={draft} onChange={setDraft} fieldPrefix="complete-stage" />

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={saving || !draft.occurred_at || !draft.stage_label.trim()}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
