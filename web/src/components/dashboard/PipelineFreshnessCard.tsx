'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Clock } from 'lucide-react'
import { timeAgo } from '@/lib/utils/format'

interface PipelineFreshnessCardProps {
  lastRunAt?: string | null
  newJobsToday: number
}

function formatTimestamp(iso: string) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getFreshnessState(lastRunAt?: string | null) {
  if (!lastRunAt) {
    return {
      label: 'Never run',
      className: 'border-border/50 bg-muted/20 text-muted-foreground',
    }
  }

  const timestamp = new Date(lastRunAt).getTime()
  if (Number.isNaN(timestamp)) {
    return {
      label: 'Unknown',
      className: 'border-border/50 bg-muted/20 text-muted-foreground',
    }
  }

  const diffHours = (Date.now() - timestamp) / 3_600_000
  if (diffHours >= 24) {
    return {
      label: 'Stale',
      className: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400',
    }
  }

  return {
    label: 'Fresh',
    className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  }
}

export function PipelineFreshnessCard({ lastRunAt, newJobsToday }: PipelineFreshnessCardProps) {
  const state = getFreshnessState(lastRunAt)

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md shadow-sm">
      <CardHeader className="border-b border-border/40 pb-4">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary" />
            Pipeline Freshness
          </CardTitle>
          <Badge variant="outline" className={state.className}>
            {state.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        {lastRunAt ? (
          <>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                Last Sync
              </div>
              <div className="mt-1 text-2xl font-black tracking-tight text-foreground">
                {timeAgo(lastRunAt)}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Updated {formatTimestamp(lastRunAt)}
              </p>
            </div>

            <div className="rounded-xl border border-border/40 bg-muted/15 px-3 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                Today
              </div>
              <p className="mt-1 text-sm font-medium text-foreground">
                {newJobsToday} matching jobs today
              </p>
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-border/50 bg-muted/10 px-4 py-5">
            <p className="text-sm font-medium text-foreground">Pipeline never run</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Run the pipeline once to populate dashboard freshness data.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
