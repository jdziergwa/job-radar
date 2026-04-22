'use client'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { CalendarClock, CheckCircle2, Plus } from 'lucide-react'

export function AddStepDialog({
  open,
  onOpenChange,
  saving = false,
  onCompleted,
  onUpcoming,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  saving?: boolean
  onCompleted: () => void
  onUpcoming: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-3xl border border-border/60 bg-popover/95 shadow-2xl backdrop-blur-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <Plus className="h-4 w-4 text-primary" />
            Add Step
          </DialogTitle>
          <DialogDescription>
            Choose whether this step already happened or is planned for later.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <button
            type="button"
            onClick={onCompleted}
            disabled={saving}
            className="flex w-full items-start gap-3 rounded-2xl border border-border/50 bg-background/40 px-4 py-4 text-left transition-colors hover:border-primary/30 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span className="space-y-1">
              <span className="block text-sm font-semibold text-foreground">Completed</span>
              <span className="block text-sm text-muted-foreground">
                This step already happened.
              </span>
            </span>
          </button>

          <button
            type="button"
            onClick={onUpcoming}
            disabled={saving}
            className="flex w-full items-start gap-3 rounded-2xl border border-border/50 bg-background/40 px-4 py-4 text-left transition-colors hover:border-primary/30 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span className="space-y-1">
              <span className="block text-sm font-semibold text-foreground">Upcoming</span>
              <span className="block text-sm text-muted-foreground">
                This is the next planned step.
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
