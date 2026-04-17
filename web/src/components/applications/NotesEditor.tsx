'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Loader2, Save } from 'lucide-react'

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

  useEffect(() => {
    setDraft(notes ?? '')
  }, [notes])

  const isDirty = draft !== (notes ?? '')

  return (
    <div className="space-y-3">
      <Textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Add recruiter context, interview prep notes, follow-up reminders, or anything else worth keeping with this application."
        className="min-h-32 rounded-2xl border-border/50 bg-background/50 px-4 py-3 text-sm leading-relaxed"
      />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">Markdown-style plain text is fine here. Save is explicit.</p>
        <div className="flex items-center gap-2">
          {isDirty && (
            <Button variant="ghost" size="sm" onClick={() => setDraft(notes ?? '')} disabled={saving}>
              Reset
            </Button>
          )}
          <Button size="sm" onClick={() => void onSave(draft)} disabled={!isDirty || saving} className="gap-2">
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save Notes
          </Button>
        </div>
      </div>
    </div>
  )
}
