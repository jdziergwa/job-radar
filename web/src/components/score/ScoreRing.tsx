'use client'

import { useEffect, useState } from 'react'
import { scoreToColor, getScoreTier } from '@/lib/utils/score'

const GLOW: Record<string, string> = {
  high:   'drop-shadow(0 0 7px #22c55e99)',
  medium: 'drop-shadow(0 0 7px #f59e0b88)',
  low:    'drop-shadow(0 0 5px #ef444466)',
}

export function ScoreRing({
  score,
  size = 48,
  strokeWidth = 4,
  animated = true
}: {
  score: number | null
  size?: number
  strokeWidth?: number
  animated?: boolean
}) {
  const [displayScore, setDisplayScore] = useState(0)
  const radius = (size - strokeWidth) / 2
  const circ = radius * 2 * Math.PI

  useEffect(() => {
    if (animated && score !== null) {
      const timer = setTimeout(() => setDisplayScore(score), 100)
      return () => clearTimeout(timer)
    } else {
      setDisplayScore(score ?? 0)
    }
  }, [score, animated])

  const strokePct = score !== null ? ((100 - displayScore) * circ) / 100 : circ
  const color = scoreToColor(score)
  const tier = getScoreTier(score)
  const glowFilter = score !== null ? (GLOW[tier] ?? '') : ''

  return (
    <div className="relative flex items-center justify-center font-mono font-bold" style={{ width: size, height: size }}>
      <svg
        className="absolute inset-0 rotate-[-90deg]"
        width={size}
        height={size}
        style={{ filter: glowFilter, transition: 'filter 0.6s ease' }}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          className="text-muted/20"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circ}
          strokeDashoffset={strokePct}
          className="transition-all duration-1000 ease-out"
          strokeLinecap="round"
        />
      </svg>
      <span className="text-sm z-10" style={{ color: score !== null ? color : 'currentColor' }}>
        {score !== null ? Math.round(displayScore) : '—'}
      </span>
    </div>
  )
}
