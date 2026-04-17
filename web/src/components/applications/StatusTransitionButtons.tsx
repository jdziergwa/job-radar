'use client'

import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
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
  screening: ['interviewing', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  interviewing: ['offer', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  offer: ['accepted', 'rejected_by_user'],
  accepted: ['rejected_by_user'],
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
}: {
  currentStatus: ApplicationStatus
  saving?: boolean
  onTransition: (status: ApplicationStatus, note?: string) => Promise<void> | void
  onRemove: () => Promise<void> | void
}) {
  const [pendingStatus, setPendingStatus] = useState<ApplicationStatus | null>(null)
  const [note, setNote] = useState('')
  const nextStatuses = useMemo(() => TRANSITIONS[currentStatus] ?? [], [currentStatus])

  const confirmTransition = async () => {
    if (!pendingStatus) return
    await onTransition(pendingStatus, note.trim() || undefined)
    setPendingStatus(null)
    setNote('')
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {nextStatuses.map((status) => (
          <Button
            key={status}
            variant={pendingStatus === status ? 'default' : 'outline'}
            size="sm"
            disabled={saving}
            onClick={() => {
              setPendingStatus(status)
              if (pendingStatus === status) {
                setPendingStatus(null)
                setNote('')
              }
            }}
            className="gap-2"
          >
            <ArrowRight className="h-3.5 w-3.5" />
            {LABELS[status]}
          </Button>
        ))}
      </div>

      {pendingStatus && (
        <div className="space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            <MessageSquarePlus className="h-4 w-4 text-primary" />
            Move to {LABELS[pendingStatus]}
          </div>
          <Textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note for this transition..."
            className="min-h-24 rounded-2xl border-border/50 bg-background/50"
          />
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => { setPendingStatus(null); setNote('') }} disabled={saving}>
              Cancel
            </Button>
            <Button size="sm" onClick={() => void confirmTransition()} disabled={saving} className="gap-2">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
              Confirm
            </Button>
          </div>
        </div>
      )}

      <Button
        variant="ghost"
        size="sm"
        onClick={() => void onRemove()}
        disabled={saving}
        className="gap-2 text-muted-foreground hover:text-destructive"
      >
        <Trash2 className="h-3.5 w-3.5" />
        Remove from Tracker
      </Button>
    </div>
  )
}
