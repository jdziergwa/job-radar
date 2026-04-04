'use client'

import React, { useEffect, useState } from 'react'
import { scoreToColor } from '@/lib/utils/score'

export function ScoreBar({ label, score }: { label: string, score: number }) {
  const [width, setWidth] = useState(0)
  const color = scoreToColor(score)
  
  useEffect(() => {
    const timer = setTimeout(() => setWidth(score), 500)
    return () => clearTimeout(timer)
  }, [score])

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center text-xs font-mono">
        <span className="text-muted-foreground uppercase tracking-wider">{label.replace(/_/g, ' ')}</span>
        <span className="font-bold tabular-nums" style={{ color }}>{score}%</span>
      </div>
      <div className="h-1.5 w-full bg-secondary/50 overflow-hidden rounded-full border border-border/10 shadow-inner">
        <div 
          className="h-full rounded-full transition-all duration-1000 ease-in-out" 
          style={{ 
            width: `${width}%`, 
            backgroundColor: color,
            boxShadow: `0 0 8px ${color}33`
          }}
        />
      </div>
    </div>
  )
}
