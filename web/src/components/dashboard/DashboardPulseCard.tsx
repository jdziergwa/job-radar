'use client'

import Link from 'next/link'
import type { components } from '@/lib/api/types'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { timeAgo } from '@/lib/utils/format'
import { CalendarDays, Target } from 'lucide-react'

type StatsOverview = components['schemas']['StatsOverview']
type PipelineFunnelStats = components['schemas']['PipelineFunnelStats']

interface DashboardPulseCardProps {
  stats?: StatsOverview | null
  funnelData?: PipelineFunnelStats | null
  lastRunAt?: string | null
  loading?: boolean
  className?: string
}

function getFreshnessState(lastRunAt?: string | null) {
  if (!lastRunAt) {
    return { label: 'Awaiting run', className: 'border-border/50 bg-muted/20 text-muted-foreground' }
  }

  const timestamp = new Date(lastRunAt).getTime()
  if (Number.isNaN(timestamp)) {
    return { label: 'Unknown', className: 'border-border/50 bg-muted/20 text-muted-foreground' }
  }

  const diffHours = (Date.now() - timestamp) / 3_600_000
  if (diffHours >= 24) {
    return { label: 'Stale', className: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400' }
  }

  return { label: 'Fresh', className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' }
}

function ranToday(lastRunAt?: string | null) {
  if (!lastRunAt) return false
  const timestamp = new Date(lastRunAt)
  if (Number.isNaN(timestamp.getTime())) return false
  return timestamp.toDateString() === new Date().toDateString()
}

function getHeadline(newToday: number, pending: number, highPriorityToday: number, highPriorityThisWeek: number, hasRun: boolean) {
  if (!hasRun) return 'Ready to start your search'
  if (highPriorityToday > 0) return `${highPriorityToday} strong matches surfaced today`
  if (highPriorityThisWeek > 0) return `${highPriorityThisWeek} strong matches surfaced this week`
  if (pending > 0) return `${pending} jobs are waiting for review`
  if (newToday > 0) return `${newToday} fresh roles landed today`
  return 'Search pulse is quiet right now'
}

function getSupportingCopy(newToday: number, pending: number, highPriorityToday: number, highPriorityThisWeek: number, hasRun: boolean) {
  if (!hasRun) {
    return 'Run the pipeline to fetch, score, and surface your first batch of job matches.'
  }
  if (highPriorityToday > 0 && pending > 0) {
    return `These are today’s strongest scored matches so far, with ${pending} more jobs still waiting for review.`
  }
  if (highPriorityToday > 0 && newToday > 0) {
    return `These are today’s strongest scored matches so far, with ${newToday} fresh roles added in the latest run.`
  }
  if (highPriorityToday > 0) {
    return 'These are the strongest scored matches from today’s pipeline activity, ready to review first.'
  }
  if (highPriorityThisWeek > 0 && pending > 0) {
    return `These are the strongest scored matches so far this week, with ${pending} more jobs still waiting for review.`
  }
  if (highPriorityThisWeek > 0 && newToday > 0) {
    return `These are the strongest scored matches so far this week, plus ${newToday} fresh roles added today.`
  }
  if (highPriorityThisWeek > 0) {
    return 'These are the strongest scored matches from the last 7 days, ready to review first.'
  }
  if (pending > 0) {
    return `No strong matches yet. ${pending} jobs are still waiting to be scored.`
  }
  if (newToday > 0) {
    return `No strong matches yet. ${newToday} new roles landed today and may still surface after scoring.`
  }
  return 'No strong matches surfaced this week. Check the broader board or run the pipeline again.'
}

interface StatTile {
  label: string
  value: number
  copy: string
  href: string
  icon: typeof CalendarDays
}

function StatRow({ label, value, copy, href, icon: Icon }: StatTile) {
  return (
    <Link
      href={href}
      className="flex items-start justify-between gap-3 rounded-xl border border-border/40 bg-background/45 px-4 py-3 shadow-sm transition-colors hover:border-primary/25 hover:bg-primary/5"
    >
      <div className="flex min-w-0 items-start gap-3">
        <div className="rounded-lg bg-primary/10 p-2 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/65">
            {label}
          </div>
          <p className="mt-1 max-w-[18rem] text-[11px] leading-relaxed text-muted-foreground">
            {copy}
          </p>
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="text-3xl font-black tracking-tight tabular-nums">{value}</div>
      </div>
    </Link>
  )
}

export function DashboardPulseCard({
  stats,
  funnelData,
  lastRunAt,
  loading = false,
  className,
}: DashboardPulseCardProps) {
  const newToday = stats?.new_today ?? 0
  const highPriorityToday = stats?.high_priority_today ?? 0
  const newThisWeek = stats?.new_this_week ?? 0
  const pending = stats?.pending ?? 0
  const highPriorityThisWeek = funnelData?.high_priority ?? 0
  const freshness = getFreshnessState(lastRunAt)
  const hasRunToday = ranToday(lastRunAt)
  const headline = getHeadline(newToday, pending, highPriorityToday, highPriorityThisWeek, !!lastRunAt)
  const supportingCopy = getSupportingCopy(newToday, pending, highPriorityToday, highPriorityThisWeek, !!lastRunAt)

  if (loading) {
    return (
      <Card className={cn("overflow-hidden border-border/50 bg-background/30 backdrop-blur-md", className)}>
        <CardContent className="space-y-5 p-5 sm:p-6">
          <div className="h-5 w-40 animate-pulse rounded-full bg-muted" />
          <div className="h-16 w-72 animate-pulse rounded-xl bg-muted" />
          <div className="h-10 w-full animate-pulse rounded-xl bg-muted/70" />
          <div className="grid gap-4 lg:grid-cols-2">
            {[1, 2].map((section) => (
              <div key={section} className="rounded-2xl border border-border/40 bg-background/35 p-4">
                <div className="mb-4 h-4 w-20 animate-pulse rounded bg-muted" />
                <div className="space-y-3">
                  {[1, 2].map((item) => (
                    <div key={item} className="h-24 animate-pulse rounded-xl bg-muted/70" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  const todayTiles: StatTile[] = [
    {
      label: 'New Today',
      value: newToday,
      copy: !lastRunAt
        ? 'Run the pipeline to check today’s jobs.'
        : hasRunToday
          ? 'Found in today’s pipeline run.'
          : `No scan today yet. Last sync ${timeAgo(lastRunAt)}.`,
      href: '/jobs?status=new,scored&today_only=true',
      icon: CalendarDays,
    },
    {
      label: 'Strong Matches',
      value: highPriorityToday,
      copy: !lastRunAt
        ? 'Today’s strong matches will appear after the next run.'
        : hasRunToday
          ? 'High-fit roles surfaced in today’s run.'
          : `Today’s shortlist is stale until the next scan.`,
      href: '/jobs?status=scored&min_score=80&today_only=true',
      icon: Target,
    },
  ]

  const weekTiles: StatTile[] = [
    {
      label: 'New This Week',
      value: newThisWeek,
      copy: 'Fresh matches surfaced in the last 7 days.',
      href: '/jobs?status=new,scored',
      icon: CalendarDays,
    },
    {
      label: 'Strong Matches',
      value: highPriorityThisWeek,
      copy: 'Best-fit scored roles from the last 7 days.',
      href: '/jobs?status=scored&min_score=80',
      icon: Target,
    },
  ]

  return (
    <Card className={cn("overflow-hidden border-border/50 bg-background/30 shadow-sm backdrop-blur-md", className)}>
      <CardContent className="space-y-5 p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-primary/20 bg-primary/10 text-primary">
            Search Pulse
          </Badge>
          <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground/70">
            {lastRunAt ? `Synced ${timeAgo(lastRunAt)}` : 'No completed run yet'}
          </span>
          <Badge variant="outline" className={freshness.className}>
            {freshness.label}
          </Badge>
        </div>

        <div className="space-y-3">
          <h2 className="max-w-3xl text-3xl font-black tracking-tight sm:text-4xl">
            {headline}
          </h2>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            {supportingCopy}
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {[
            { title: 'Today', tiles: todayTiles },
            { title: 'This Week', tiles: weekTiles },
          ].map(({ title, tiles }) => (
            <section key={title} className="rounded-2xl border border-border/40 bg-background/35 p-4 shadow-sm">
              <div className="mb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/65">
                  {title}
                </p>
              </div>
              <div className="space-y-3">
                {tiles.map((tile) => (
                  <StatRow key={`${title}-${tile.label}`} {...tile} />
                ))}
              </div>
            </section>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
