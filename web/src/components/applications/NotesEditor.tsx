'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Expand, Loader2, Save } from 'lucide-react'

export function NotesEditor({
  notes,
  saving = false,
  onSave,
}: {
  notes?: string | null
  saving?: boolean
  onSave: (notes: string) => Promise<void> | void
}) {
  const [draft, setDraft] = useState(notes ?? '')
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setDraft(notes ?? '')
  }, [notes])

  const isDirty = draft !== (notes ?? '')

  const handleSave = async () => {
    await onSave(draft)
  }

  return (
    <>
      <div className="space-y-2.5">
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Add recruiter context, interview prep notes, follow-up reminders, or anything else worth keeping with this application."
          className="h-32 resize-none overflow-y-auto rounded-2xl border-border/40 bg-background/35 px-4 py-3 text-sm leading-relaxed"
        />
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] text-muted-foreground">Use this for recruiter context, prep notes, or follow-ups.</p>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setExpanded(true)} className="gap-2 text-muted-foreground">
              <Expand className="h-3.5 w-3.5" />
              Expand
            </Button>
            {isDirty && (
              <Button variant="ghost" size="sm" onClick={() => setDraft(notes ?? '')} disabled={saving}>
                Reset
              </Button>
            )}
            <Button size="sm" onClick={() => void handleSave()} disabled={!isDirty || saving} className="gap-2">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Save Notes
            </Button>
          </div>
        </div>
      </div>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="sm:max-w-3xl" showCloseButton>
          <DialogHeader>
            <DialogTitle>Edit Notes</DialogTitle>
            <DialogDescription>
              Use the expanded editor when you need more room for recruiter context, prep notes, or longer application history.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Add recruiter context, interview prep notes, follow-up reminders, or anything else worth keeping with this application."
            className="h-[50vh] min-h-[320px] resize-none overflow-y-auto rounded-2xl border-border/50 bg-background/50 px-4 py-3 text-sm leading-relaxed"
          />
          <DialogFooter>
            {isDirty && (
              <Button variant="ghost" onClick={() => setDraft(notes ?? '')} disabled={saving}>
                Reset
              </Button>
            )}
            <Button onClick={() => void handleSave()} disabled={!isDirty || saving} className="gap-2">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Save Notes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
