'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  APPLICATION_STAGE_TRANSITIONS,
  getApplicationStageLabel,
  getTodayDateInputValue,
  type ApplicationStatus,
} from '@/lib/applications/stages'
import { Loader2, XCircle } from 'lucide-react'

const NEGATIVE_OUTCOME_OPTIONS: ApplicationStatus[] = ['rejected_by_company', 'rejected_by_user', 'ghosted']

export function NegativeOutcomeDialog({
  open,
  onOpenChange,
  saving = false,
  currentStatus,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  saving?: boolean
  currentStatus: ApplicationStatus | null
  onSubmit: (payload: { status: ApplicationStatus; note?: string; occurred_at: string }) => Promise<void> | void
}) {
  const availableOptions = useMemo(() => {
    const transitions = currentStatus ? APPLICATION_STAGE_TRANSITIONS[currentStatus] ?? [] : []
    const filtered = transitions.filter((status): status is ApplicationStatus => NEGATIVE_OUTCOME_OPTIONS.includes(status))
    return filtered.length > 0 ? filtered : ['rejected_by_company']
  }, [currentStatus])

  const [selectedStatus, setSelectedStatus] = useState<ApplicationStatus>(availableOptions[0])
  const [occurredAt, setOccurredAt] = useState(getTodayDateInputValue())
  const [note, setNote] = useState('')

  useEffect(() => {
    setSelectedStatus(availableOptions[0])
    setOccurredAt(getTodayDateInputValue())
    setNote('')
  }, [availableOptions, open])

  const submit = async () => {
    await onSubmit({ status: selectedStatus, note: note.trim() || undefined, occurred_at: occurredAt })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-3xl border border-border/60 bg-popover/95 shadow-2xl backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <XCircle className="h-4 w-4 text-destructive" />
            Close Application
          </DialogTitle>
          <DialogDescription>
            Choose how you want to close out this application and add any helpful context.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="negative-outcome-status">Outcome</Label>
            <Select value={selectedStatus} onValueChange={(value) => value && setSelectedStatus(value as ApplicationStatus)}>
              <SelectTrigger id="negative-outcome-status" className="h-12 w-full rounded-2xl border-border/50 bg-background/50 px-4">
                <SelectValue placeholder="Select outcome">
                  {getApplicationStageLabel(selectedStatus)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {availableOptions.map((status) => (
                  <SelectItem key={status} value={status}>
                    {getApplicationStageLabel(status)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="negative-outcome-date">Date</Label>
            <Input
              id="negative-outcome-date"
              type="date"
              value={occurredAt}
              onChange={(event) => setOccurredAt(event.target.value)}
              className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="negative-outcome-note">Note</Label>
            <Textarea
              id="negative-outcome-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Optional context about why this application is closing..."
              className="min-h-28 rounded-2xl border-border/50 bg-background/50 resize-none"
            />
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={saving || !occurredAt} className="gap-2">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
            Save Close-Out
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
