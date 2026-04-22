'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getTodayDateInputValue, normalizeTrackerDateForInput } from '@/lib/applications/stages'
import { Loader2, MailCheck } from 'lucide-react'

export function ResponseMilestoneDialog({
  open,
  onOpenChange,
  saving = false,
  initialDate,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  saving?: boolean
  initialDate?: string | null
  onSubmit: (payload: { response_date: string }) => Promise<void> | void
}) {
  const [responseDate, setResponseDate] = useState(normalizeTrackerDateForInput(initialDate) || getTodayDateInputValue())

  useEffect(() => {
    setResponseDate(normalizeTrackerDateForInput(initialDate) || getTodayDateInputValue())
  }, [initialDate, open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-3xl border border-border/60 bg-popover/95 shadow-2xl backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <MailCheck className="h-4 w-4 text-primary" />
            Record Response
          </DialogTitle>
          <DialogDescription>
            Capture when the recruiter or hiring team replied, even if the next stage is only scheduled.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-2">
          <Label htmlFor="response-date">Response Date</Label>
          <Input
            id="response-date"
            type="date"
            value={responseDate}
            onChange={(event) => setResponseDate(event.target.value)}
            className="h-12 rounded-2xl border-border/50 bg-background/50 px-4"
          />
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void onSubmit({ response_date: responseDate })} disabled={saving || !responseDate}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MailCheck className="mr-2 h-4 w-4" />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
