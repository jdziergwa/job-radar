'use client'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { CalendarClock, MailCheck, XCircle } from 'lucide-react'

export function AppliedResponseDialog({
  open,
  onOpenChange,
  saving = false,
  onPositive,
  onNegative,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  saving?: boolean
  onPositive: () => void
  onNegative: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-3xl border border-border/60 bg-popover/95 shadow-2xl backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <MailCheck className="h-4 w-4 text-primary" />
            Update Outcome
          </DialogTitle>
          <DialogDescription>
            Move the process forward, or close it out if it ended here.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <button
            type="button"
            onClick={onPositive}
            disabled={saving}
            className="flex w-full items-start gap-3 rounded-2xl border border-border/50 bg-background/40 px-4 py-4 text-left transition-colors hover:border-primary/30 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span className="space-y-1">
              <span className="block text-sm font-semibold text-foreground">Positive Response</span>
              <span className="block text-sm text-muted-foreground">
                Continue to scheduling the next step or capturing an offer.
              </span>
            </span>
          </button>

          <button
            type="button"
            onClick={onNegative}
            disabled={saving}
            className="flex w-full items-start gap-3 rounded-2xl border border-border/50 bg-background/40 px-4 py-4 text-left transition-colors hover:border-destructive/30 hover:bg-destructive/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <span className="space-y-1">
              <span className="block text-sm font-semibold text-foreground">Close Application</span>
              <span className="block text-sm text-muted-foreground">
                Mark it as rejected, withdrawn, or ghosted.
              </span>
            </span>
          </button>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
