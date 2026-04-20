'use client'

import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { ArrowRight, Loader2, MessageSquarePlus, Trash2 } from 'lucide-react'

export type ApplicationStatus =
  | 'applied'
  | 'screening'
  | 'interviewing'
  | 'offer'
  | 'accepted'
  | 'rejected_by_company'
  | 'rejected_by_user'
  | 'ghosted'

const TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  applied: ['screening', 'interviewing', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  screening: ['applied', 'interviewing', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  interviewing: ['screening', 'offer', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  offer: ['interviewing', 'accepted', 'rejected_by_user'],
  accepted: ['offer', 'rejected_by_user'],
  rejected_by_company: ['applied'],
  rejected_by_user: ['applied'],
  ghosted: ['screening', 'interviewing'],
}

const LABELS: Record<ApplicationStatus, string> = {
  applied: 'Applied',
  screening: 'Screening',
  interviewing: 'Interviewing',
  offer: 'Offer',
  accepted: 'Accepted',
  rejected_by_company: 'Rejected by Company',
  rejected_by_user: 'Withdrawn',
  ghosted: 'Ghosted',
}

export function StatusTransitionButtons({
  currentStatus,
  saving = false,
  onTransition,
  onRemove,
  open,
  onOpenChange,
  showTrigger = true,
}: {
  currentStatus: ApplicationStatus
  saving?: boolean
  onTransition: (status: ApplicationStatus, note?: string) => Promise<void> | void
  onRemove: () => Promise<void> | void
  open?: boolean
  onOpenChange?: (open: boolean) => void
  showTrigger?: boolean
}) {
  const [internalOpen, setInternalOpen] = useState(false)
  const [pendingStatus, setPendingStatus] = useState<ApplicationStatus | null>(null)
  const [note, setNote] = useState('')
  const nextStatuses = useMemo(() => TRANSITIONS[currentStatus] ?? [], [currentStatus])
  const dialogOpen = open ?? internalOpen

  const confirmTransition = async () => {
    if (!pendingStatus) return
    await onTransition(pendingStatus, note.trim() || undefined)
    closeTransitionDialog(false)
  }

  const closeTransitionDialog = (open: boolean) => {
    if (onOpenChange) onOpenChange(open)
    else setInternalOpen(open)

    if (!open) {
      setPendingStatus(null)
      setNote('')
    }
  }

  return (
    <div className="space-y-3">
      {showTrigger && (
        <Button
          variant="outline"
          size="sm"
          disabled={saving}
          onClick={() => closeTransitionDialog(true)}
          className="gap-2"
        >
          <ArrowRight className="h-3.5 w-3.5" />
          Change Status
        </Button>
      )}

      <div className="border-t border-border/35 pt-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void onRemove()}
          disabled={saving}
          className="gap-2 text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete Tracker History
        </Button>
      </div>

      <Dialog open={dialogOpen} onOpenChange={closeTransitionDialog}>
        <DialogContent className="sm:max-w-lg" showCloseButton>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquarePlus className="h-4 w-4 text-primary" />
              Change Status
            </DialogTitle>
            <DialogDescription>
              Choose the next valid stage for this application, including stepping back if you clicked the wrong status. You can add an optional note to the timeline.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-wrap gap-2">
            {nextStatuses.map((status) => (
              <Button
                key={status}
                variant={pendingStatus === status ? 'default' : 'outline'}
                size="sm"
                disabled={saving}
                onClick={() => setPendingStatus(status)}
                className="gap-2"
              >
                <ArrowRight className="h-3.5 w-3.5" />
                {LABELS[status]}
              </Button>
            ))}
          </div>
          <Textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note for this transition..."
            className="min-h-28 rounded-2xl border-border/50 bg-background/50"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => closeTransitionDialog(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={() => void confirmTransition()} disabled={saving || !pendingStatus} className="gap-2">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
