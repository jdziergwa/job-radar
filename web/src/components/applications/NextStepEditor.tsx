'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Loader2, Save, Trash2 } from 'lucide-react'

export function NextStepEditor({
  nextStep,
  nextStepDate,
  saving = false,
  onSave,
}: {
  nextStep?: string | null
  nextStepDate?: string | null
  saving?: boolean
  onSave: (payload: { next_step: string | null; next_step_date: string | null }) => Promise<void> | void
}) {
  const [draftStep, setDraftStep] = useState(nextStep ?? '')
  const [draftDate, setDraftDate] = useState(nextStepDate ?? '')

  useEffect(() => {
    setDraftStep(nextStep ?? '')
  }, [nextStep])

  useEffect(() => {
    setDraftDate(nextStepDate ?? '')
  }, [nextStepDate])

  const normalizedStep = draftStep.trim()
  const normalizedDate = draftDate || ''
  const initialStep = nextStep ?? ''
  const initialDate = nextStepDate ?? ''
  const isDirty = normalizedStep !== initialStep || normalizedDate !== initialDate

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]">
        <Input
          value={draftStep}
          onChange={(event) => setDraftStep(event.target.value)}
          placeholder="Technical interview, recruiter follow-up, salary call..."
          className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
        />
        <Input
          type="date"
          value={draftDate}
          onChange={(event) => setDraftDate(event.target.value)}
          className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
        />
      </div>

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">Leave either field empty if the process is currently waiting on the company.</p>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={saving || (!normalizedStep && !normalizedDate)}
            onClick={() => void onSave({ next_step: null, next_step_date: null })}
            className="gap-2 text-muted-foreground"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </Button>
          <Button
            size="sm"
            disabled={saving || !isDirty}
            onClick={() =>
              void onSave({
                next_step: normalizedStep || null,
                next_step_date: normalizedDate || null,
              })
            }
            className="gap-2"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save Next Step
          </Button>
        </div>
      </div>
    </div>
  )
}
