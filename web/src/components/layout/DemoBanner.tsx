'use client'

import { useEffect, useState } from 'react'
import { BASE_PATH, IS_DEMO } from '@/lib/demo-mode'

export function DemoBanner() {
  const [dateLabel, setDateLabel] = useState<string | null>(null)

  useEffect(() => {
    if (!IS_DEMO) return

    fetch(`${BASE_PATH}/demo-data/snapshot.json`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error('Failed to load snapshot metadata')
        }
        return response.json()
      })
      .then((data: { generated_at?: string }) => {
        if (!data.generated_at) return

        setDateLabel(
          new Date(data.generated_at).toLocaleDateString('en-GB', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
          }),
        )
      })
      .catch(() => {})
  }, [])

  if (!IS_DEMO) {
    return null
  }

  return (
    <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-center text-xs text-amber-950 dark:text-amber-100">
      <strong className="font-semibold">Demo</strong>
      {dateLabel ? ` - snapshot from ${dateLabel}` : ' - static snapshot'}
    </div>
  )
}
