'use client'

import { Card, CardContent } from '@/components/ui/card'
import { BriefcaseBusiness, Clock3, Goal, MessageSquareReply } from 'lucide-react'

interface ApplicationStatsData {
  total: number
  active_count: number
  offers_count: number
  response_rate: number
  avg_time_to_response_days: number | null
  source_breakdown: Record<string, number>
}

function StatCard({
  label,
  value,
  description,
  icon: Icon,
  accent,
}: {
  label: string
  value: string
  description: string
  icon: typeof BriefcaseBusiness
  accent: string
}) {
  return (
    <Card className="border-border/50 bg-card/60 shadow-xl backdrop-blur-xl">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">
              {label}
            </div>
            <div className="text-3xl font-black tracking-tight text-foreground">{value}</div>
            <p className="max-w-[18rem] text-sm leading-relaxed text-muted-foreground">{description}</p>
          </div>
          <div className={`rounded-2xl border px-3 py-3 ${accent}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function ApplicationStats({ stats }: { stats: ApplicationStatsData | null }) {
  const pipelineCount = stats?.source_breakdown?.pipeline ?? 0
  const manualCount = stats?.source_breakdown?.manual ?? 0

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Active Applications"
          value={String(stats?.active_count ?? 0)}
          description="Live processes still waiting on a next step, reply, or decision."
          icon={BriefcaseBusiness}
          accent="border-sky-500/20 bg-sky-500/10 text-sky-600 dark:text-sky-300"
        />
        <StatCard
          label="Offers"
          value={String(stats?.offers_count ?? 0)}
          description="Applications that reached offer stage or already converted into accepted roles."
          icon={Goal}
          accent="border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
        />
        <StatCard
          label="Response Rate"
          value={`${stats?.response_rate ?? 0}%`}
          description="Share of applications where a company responded instead of silently stalling."
          icon={MessageSquareReply}
          accent="border-indigo-500/20 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300"
        />
        <StatCard
          label="Avg. Time to Response"
          value={stats?.avg_time_to_response_days != null ? `${stats.avg_time_to_response_days}d` : '—'}
          description="Average time from application submission to the first company response."
          icon={Clock3}
          accent="border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-300"
        />
      </div>

      <div className="rounded-2xl border border-border/40 bg-background/40 px-4 py-3 text-xs text-muted-foreground shadow-sm">
        {stats?.total ?? 0} tracked applications total. {pipelineCount} came from the radar pipeline and {manualCount} were imported manually.
      </div>
    </div>
  )
}
