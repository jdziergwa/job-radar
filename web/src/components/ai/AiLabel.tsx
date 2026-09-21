'use client'

import type { AiConfig, AiTask } from '@/lib/ai/use-ai-config'

/** "AI: <LLM Provider> · <Model>" for a task, or an "AI not configured" notice. */
export function AiLabel({ config, task, className }: { config: AiConfig | null; task: AiTask; className?: string }) {
  if (!config) return <span className={className}>AI</span>
  if (!config.configured || !config.models) {
    return (
      <span className={className} title={config.error ?? undefined}>
        AI not configured
      </span>
    )
  }
  return (
    <span className={className}>
      AI: {config.provider_display_name} · {config.models[task]}
    </span>
  )
}
