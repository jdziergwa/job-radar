'use client'

import { useEffect, useRef, useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { LucideIcon } from 'lucide-react'

export interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  loading?: boolean
}

function useCountUp(target: number, duration = 900) {
  const [count, setCount] = useState(0)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setCount(Math.round(eased * target))
      if (progress < 1) rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [target, duration])

  return count
}

export function MetricCard({ title, value, subtitle, icon: Icon, loading }: MetricCardProps) {
  const numericTarget = typeof value === 'number' ? value : null
  const animated = useCountUp(numericTarget ?? 0)
  const displayValue = numericTarget !== null ? animated : value

  if (loading) {
    return (
      <Card className="overflow-hidden border-border/50 bg-background/40 backdrop-blur-md">
        <CardContent className="p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="h-10 w-10 animate-pulse rounded-xl bg-muted" />
            <div className="h-4 w-20 animate-pulse rounded bg-muted mt-1" />
          </div>
          <div className="h-10 w-20 animate-pulse rounded bg-muted mb-2" />
          <div className="h-3 w-32 animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="relative overflow-hidden border-border/50 bg-background/40 backdrop-blur-md hover:bg-background/60 hover:border-primary/20 transition-all duration-300 group">
      {/* Subtle corner glow on hover */}
      <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 -translate-y-1/2 translate-x-1/2 pointer-events-none" />
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="bg-primary/10 p-2.5 rounded-xl group-hover:bg-primary/20 transition-colors duration-300">
            <Icon className="h-5 w-5 text-primary" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/60 mt-1">{title}</span>
        </div>
        <div className="text-4xl font-black tracking-tight tabular-nums">{displayValue}</div>
        {subtitle && <p className="text-xs text-muted-foreground mt-1.5">{subtitle}</p>}
      </CardContent>
    </Card>
  )
}
