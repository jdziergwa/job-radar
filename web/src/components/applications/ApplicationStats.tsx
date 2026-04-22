'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  AlertTriangle,
  ArrowRightLeft,
  Clock3,
  Hash,
  HelpCircle,
  Target,
  Timer,
  TrendingUp,
} from 'lucide-react'

interface ApplicationStatsData {
  total: number
  active_count: number
  offers_count: number
  response_rate: number
  avg_time_to_response_days: number | null
  screen_rate: number
  avg_days_to_screen: number | null
  open_offers_count: number
  avg_days_from_screen_to_interview: number | null
  avg_days_to_reject: number | null
  needs_attention_count: number
  interview_conversion: number
  offer_conversion: number
  avg_process_days: number | null
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
  icon: typeof Hash
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

function MiniStat({
  label,
  value,
  tooltip,
}: {
  label: string
  value: string
  tooltip: string
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Tooltip>
        <TooltipTrigger className="cursor-help text-muted-foreground/40 transition-colors hover:text-muted-foreground/70">
          <HelpCircle className="h-3 w-3" />
        </TooltipTrigger>
        <TooltipContent side="top">
          <p>{tooltip}</p>
        </TooltipContent>
      </Tooltip>
      <span className="ml-auto text-sm font-semibold text-foreground">{value}</span>
    </div>
  )
}

export function ApplicationStats({ stats }: { stats: ApplicationStatsData | null }) {
  const pipelineCount = stats?.source_breakdown?.pipeline ?? 0
  const manualCount = stats?.source_breakdown?.manual ?? 0

  return (
    <TooltipProvider>
      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
          <StatCard
            label="Total Applications"
            value={String(stats?.total ?? 0)}
            description="All tracked applications across every stage and outcome."
            icon={Hash}
            accent="border-sky-500/20 bg-sky-500/10 text-sky-600 dark:text-sky-300"
          />
          <StatCard
            label="Screen Rate"
            value={`${stats?.screen_rate ?? 0}%`}
            description="Share of applications that progressed to screening or beyond."
            icon={Target}
            accent="border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
          />
          <StatCard
            label="Avg. Days to Screen"
            value={stats?.avg_days_to_screen != null ? `${stats.avg_days_to_screen}d` : '—'}
            description="Average time from application to the first screening invite."
            icon={Clock3}
            accent="border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-300"
          />
          <StatCard
            label="Avg. Days to Reject"
            value={stats?.avg_days_to_reject != null ? `${stats.avg_days_to_reject}d` : '—'}
            description="Average days to rejection for those that never reached screening."
            icon={Timer}
            accent="border-rose-500/20 bg-rose-500/10 text-rose-600 dark:text-rose-300"
          />
          <StatCard
            label="Total Offers"
            value={String(stats?.offers_count ?? 0)}
            description="Total number of job offers received in this funnel."
            icon={TrendingUp}
            accent="border-indigo-500/20 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300"
          />
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Card className="border-border/40 bg-card/40 shadow-md backdrop-blur-lg">
            <CardContent className="p-4">
              <MiniStat
                label="Active Applications"
                value={String(stats?.active_count ?? 0)}
                tooltip="Total count of applications currently in progress (Applied, Screening, or Interviewing)."
              />
            </CardContent>
          </Card>
          <Card className="border-border/40 bg-card/40 shadow-md backdrop-blur-lg">
            <CardContent className="p-4">
              <MiniStat
                label="Pending Replies"
                value={String(stats?.pending_replies_count ?? 0)}
                tooltip="Number of applications currently in the 'Applied' stage, waiting for a recruiter response."
              />
            </CardContent>
          </Card>
          <Card className="border-border/40 bg-card/40 shadow-md backdrop-blur-lg">
            <CardContent className="p-4">
              <MiniStat
                label="Stalled Applications"
                value={String(stats?.needs_attention_count ?? 0)}
                tooltip="Applications that have exceeded momentum benchmarks (7+ days of silence) or been ghosted."
              />
            </CardContent>
          </Card>
          <Card className="border-border/40 bg-card/40 shadow-md backdrop-blur-lg">
            <CardContent className="p-4">
              <MiniStat
                label="Avg. Days from Screen to Interview"
                value={stats?.avg_days_from_screen_to_interview != null ? `${stats.avg_days_from_screen_to_interview}d` : '—'}
                tooltip="Average days from a screening call to receiving a first interview invite."
              />
            </CardContent>
          </Card>
          <Card className="border-border/40 bg-card/40 shadow-md backdrop-blur-lg">
            <CardContent className="p-4">
              <MiniStat
                label="Avg. Days to Decision"
                value={stats?.avg_process_days != null ? `${stats.avg_process_days}d` : '—'}
                tooltip="Average days from application until a definitive final outcome (Offer or Rejection). Excludes ghosted applications."
              />
            </CardContent>
          </Card>
        </div>

        <div className="rounded-2xl border border-border/40 bg-background/40 px-4 py-3 text-xs text-muted-foreground shadow-sm">
          {stats?.total ?? 0} tracked applications total. {pipelineCount} came from the radar pipeline and {manualCount} were imported manually.
        </div>
      </div>
    </TooltipProvider>
  )
}
