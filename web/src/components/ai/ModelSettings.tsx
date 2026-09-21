'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api/client'
import { useAiConfig, type AiConfig, type AiTask } from '@/lib/ai/use-ai-config'

const TASKS: { task: AiTask; label: string }[] = [
  { task: 'scoring', label: 'Scoring' },
  { task: 'wizard', label: 'CV wizard' },
  { task: 'stats', label: 'Stats insight' },
]

/** Per-task Model overrides for the active LLM Provider. Keys are env-only and never shown. */
export function ModelSettings() {
  const loaded = useAiConfig()
  const [config, setConfig] = useState<AiConfig | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<AiTask | null>(null)

  useEffect(() => {
    if (loaded) setConfig(loaded)
  }, [loaded])

  const save = async (task: AiTask, model: string | null) => {
    setBusy(task)
    try {
      const { data, error } = await api.PUT('/api/ai-config/models/{task}', {
        params: { path: { task } },
        body: { model },
      })
      if (data) {
        setConfig(data)
        setDrafts(d => ({ ...d, [task]: '' }))
        toast.success(model ? `${task} Model set to ${model}` : `${task} Model override cleared`)
      } else {
        const detail = (error as { detail?: unknown } | undefined)?.detail
        toast.error(typeof detail === 'string' ? detail : 'Could not save Model')
      }
    } catch {
      toast.error('Could not reach the API')
    } finally {
      setBusy(null)
    }
  }

  if (!config) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (!config.configured || !config.models) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-amber-500">
        AI not configured{config.error ? `: ${config.error}` : ''}. Set an API key in your environment first.
        </p>
        {Object.entries(config.overrides ?? {}).map(([task, model]) => (
          <div key={task} className="flex items-center gap-3 text-sm">
            <span>{task}: {model} (Settings override)</span>
            <Button size="sm" variant="ghost" disabled={busy === task} onClick={() => save(task as AiTask, null)}>
              Clear
            </Button>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <p className="text-sm text-muted-foreground">
        {config.provider_display_name} Models per AI Task. A profile&apos;s <code>scoring.model</code> still wins for scoring.
        API keys are read from the environment and can&apos;t be edited here.
      </p>
      {TASKS.map(({ task, label }) => {
        const override = config.overrides?.[task]
        const draft = drafts[task] ?? ''
        return (
          <div key={task} className="flex flex-wrap items-center gap-3">
            <div className="w-32 text-sm font-medium">{label}</div>
            <div className="w-56 text-xs text-muted-foreground truncate" title={config.models![task]}>
              {config.models![task]}{override ? ' (Settings)' : ''}
            </div>
            <Input
              className="w-64"
              placeholder="Override Model name"
              value={draft}
              onChange={e => setDrafts(d => ({ ...d, [task]: e.target.value }))}
            />
            <Button size="sm" disabled={!draft.trim() || busy === task} onClick={() => save(task, draft.trim())}>
              Set
            </Button>
            <Button size="sm" variant="ghost" disabled={!override || busy === task} onClick={() => save(task, null)}>
              Clear
            </Button>
          </div>
        )
      })}
    </div>
  )
}
