'use client'

import { aiTaskBlock, type AiConfig, type AiTask } from '@/lib/ai/use-ai-config'

/** "AI: <LLM Provider> · <Model>" for a task, or the reason it's unavailable. */
export function AiLabel({ config, task, className }: { config: AiConfig | null; task: AiTask; className?: string }) {
  if (!config) return <span className={className}>AI</span>
  const block = aiTaskBlock(config, task)
  if (block !== null || !config.models) {
    return (
      <span className={className} title={block?.reason ?? config.error ?? undefined}>
        {block?.label ?? 'AI not configured'}
      </span>
    )
  }
  return (
    <span className={className}>
      AI: {config.provider_display_name} · {config.models[task]}
    </span>
  )
}
