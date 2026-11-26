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
