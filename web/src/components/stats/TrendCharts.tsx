'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartConfig,
} from '@/components/ui/chart'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { BarChart3, Filter, Star, Target, BriefcaseBusiness } from 'lucide-react'

// --- Empty state ---

function EmptyChart({ icon: Icon, message }: { icon: typeof BarChart3; message: string }) {
  return (
    <div className="h-[240px] flex flex-col items-center justify-center gap-3 text-center">
      <div className="bg-muted/30 p-3 rounded-full">
        <Icon className="h-6 w-6 text-muted-foreground/40" />
      </div>
      <p className="text-xs text-muted-foreground/50 max-w-[200px] leading-relaxed">{message}</p>
    </div>
  )
}

// --- Jobs Activity Chart ---

type FunnelData = {
  collected: number
  passed_prefilter: number
  high_priority: number
  applied: number
}

function funnelRate(value: number, total: number) {
  if (total <= 0) {
    return '0%'
  }

  const percent = (value / total) * 100

  if (percent <= 0) {
    return '0%'
  }
  if (percent < 0.01) {
    return '<0.01%'
  }
  if (percent < 1) {
    return `${percent.toFixed(2)}%`
  }
  if (percent < 10) {
    return `${percent.toFixed(1)}%`
  }

  return `${Math.round(percent)}%`
}

export function FunnelCard({ data }: { data: FunnelData }) {
  const total = data.collected || 0
  const hasData = total > 0
  const rows = [
    {
      label: 'Collected',
      value: data.collected,
      meta: 'Raw jobs fetched',
      icon: BriefcaseBusiness,
    },
    {
      label: 'Passed Pre-filter',
      value: data.passed_prefilter,
      meta: funnelRate(data.passed_prefilter, total),
      icon: Filter,
    },
    {
      label: 'High Priority',
      value: data.high_priority,
      meta: funnelRate(data.high_priority, total),
      icon: Target,
    },
    {
      label: 'Applied',
      value: data.applied,
      meta: funnelRate(data.applied, total),
      icon: BarChart3,
    },
  ]

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Pipeline Funnel</CardTitle>
        <CardDescription className="text-xs">30-day conversion snapshot across your search funnel</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <div className="space-y-3">
            {rows.map(({ label, value, meta, icon: Icon }) => (
              <div
                key={label}
                className="flex items-center justify-between rounded-lg border border-border/30 bg-muted/10 px-3 py-2"
              >
                <div className="flex items-center gap-3">
                  <div className="rounded-md bg-primary/10 p-2">
                    <Icon className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <div>
                    <div className="text-xs font-medium text-foreground">{label}</div>
                    <div className="text-[11px] text-muted-foreground">{meta}</div>
                  </div>
                </div>
                <div className="text-xl font-bold tabular-nums">{value}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyChart icon={BarChart3} message="Run the pipeline to populate funnel conversion counts." />
        )}
      </CardContent>
    </Card>
  )
}

// --- Top Skills Chart ---

const skillsConfig = {
  count: { label: 'Mentions', color: 'var(--chart-3)' },
} satisfies ChartConfig

export function SkillsChart({ data }: { data: any[] }) {
  const displayData = data.slice(0, 10)
  const hasData = displayData.length > 0

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">In-Demand Skills</CardTitle>
        <CardDescription className="text-xs">Top keyword extraction from score reasoning</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <ChartContainer config={skillsConfig} className="h-[240px] w-full">
            <BarChart data={displayData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid horizontal={false} vertical={false} />
              <XAxis type="number" hide />
              <YAxis
                dataKey="skill"
                type="category"
                tickLine={false}
                tickMargin={10}
                axisLine={false}
                className="text-[10px] font-medium"
                width={80}
              />
              <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
              <Bar dataKey="count" fill="var(--color-count)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ChartContainer>
        ) : (
          <EmptyChart icon={Star} message="Score some jobs to see which skills appear most often." />
        )}
      </CardContent>
    </Card>
  )
}

// --- Match Distribution Chart ---

const distributionConfig = {
  count: { label: 'Jobs', color: 'var(--chart-4)' },
} satisfies ChartConfig

export function DistributionChart({ data }: { data: Record<string, number> }) {
  const displayData = [
    { range: '90-100', count: data['90-100'] || 0 },
    { range: '80-89',  count: data['80-89']  || 0 },
    { range: '70-79',  count: data['70-79']  || 0 },
    { range: '60-69',  count: data['60-69']  || 0 },
    { range: '50-59',  count: data['50-59']  || 0 },
    { range: 'Below 50', count: data['below-50'] || 0 },
  ]
  const hasData = displayData.some(d => d.count > 0)

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Match Distribution</CardTitle>
        <CardDescription className="text-xs">Score density across all processed jobs</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <ChartContainer config={distributionConfig} className="h-[240px] w-full">
            <BarChart data={displayData}>
              <CartesianGrid vertical={false} strokeDasharray="2 2" className="stroke-muted/30" />
              <XAxis dataKey="range" tickLine={false} tickMargin={10} axisLine={false} className="text-[10px]" />
              <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
              <Bar
                dataKey="count"
                radius={[4, 4, 0, 0]}
                shape={(props: any) => {
                  const { x, y, width, height, payload } = props
                  const range: string = payload?.range ?? ''
                  const fill =
                    range.startsWith('9') || range.startsWith('8') ? 'var(--color-score-high)' :
                    range.startsWith('7') || range.startsWith('6') ? 'var(--color-score-medium)' :
                    'var(--color-score-low)'
                  return <rect x={x} y={y} width={width} height={Math.max(height, 0)} rx={4} fill={fill} fillOpacity={0.85} />
                }}
              />
            </BarChart>
          </ChartContainer>
        ) : (
          <EmptyChart icon={BarChart3} message="Score some jobs to see match distribution across score bands." />
        )}
      </CardContent>
    </Card>
  )
}
