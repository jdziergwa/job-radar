'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from 'recharts'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartConfig,
} from '@/components/ui/chart'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { BarChart3, Zap, Star } from 'lucide-react'

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

const activityConfig = {
  new_jobs: { label: 'New Jobs', color: 'var(--chart-1)' },
  scored:   { label: 'Scored',   color: 'var(--chart-2)' },
} satisfies ChartConfig

export function ActivityChart({ data }: { data: any[] }) {
  const hasData = data.length > 0 && data.some(d => d.new_jobs > 0 || d.scored > 0)

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Job Activity</CardTitle>
        <CardDescription className="text-xs">Discovery vs. AI Scoring (Daily)</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <ChartContainer config={activityConfig} className="h-[240px] w-full">
            <BarChart data={data}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" className="stroke-muted/20" />
              <XAxis
                dataKey="date"
                tickLine={false}
                tickMargin={10}
                axisLine={false}
                tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="new_jobs" fill="var(--color-new_jobs)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="scored"   fill="var(--color-scored)"   radius={[4, 4, 0, 0]} />
            </BarChart>
          </ChartContainer>
        ) : (
          <EmptyChart icon={Zap} message="Run the pipeline to start tracking daily job discovery." />
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
