'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/types'

export type AiConfig = components['schemas']['AiConfig']
export type AiTask = components['schemas']['AITask']

/** Active LLM Provider and Models from the API; null until loaded (or if the API is unreachable). */
export function useAiConfig(): AiConfig | null {
  const [config, setConfig] = useState<AiConfig | null>(null)

  useEffect(() => {
    let cancelled = false
    api.GET('/api/ai-config')
      .then(({ data }) => {
        if (!cancelled && data) setConfig(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  return config
}

/** Why an AI Task can't run, as a short control label plus the full reason (for tooltips and toasts). */
export type AiTaskBlock = { label: string; reason: string }

/**
 * What blocks an AI Task: AI isn't configured ("AI not configured"), or AI is configured but that
 * task's Model has its own error ("Model unavailable"). Null when the task is available or the config
 * is still loading. The one place every AI control decides this, including its label.
 */
export function aiTaskBlock(config: AiConfig | null, task: AiTask): AiTaskBlock | null {
  if (config === null) return null
  if (!config.configured) {
    return { label: 'AI not configured', reason: `AI not configured: ${config.error ?? 'missing API key'}` }
  }
  const modelError = config.model_errors?.[task]
  return modelError ? { label: 'Model unavailable', reason: modelError } : null
}

/** The full reason an AI Task can't run, or null; see `aiTaskBlock` for the control label. */
export function aiTaskUnavailable(config: AiConfig | null, task: AiTask): string | null {
  return aiTaskBlock(config, task)?.reason ?? null
}
