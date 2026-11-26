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

/**
 * Why an AI Task can't run: AI isn't configured, or that task's Model has its own error.
 * Null when the task is available or the config is still loading. The one place every AI control decides this.
 */
export function aiTaskUnavailable(config: AiConfig | null, task: AiTask): string | null {
  if (config === null) return null
  if (!config.configured) return `AI not configured: ${config.error ?? 'missing API key'}`
  return config.model_errors?.[task] ?? null
}
