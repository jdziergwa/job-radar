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
import { AlertCircle, Globe, Star, BarChart3 } from 'lucide-react'
import { SkipReasonStat, CountryStat, SkillCount } from '@/lib/api/types'

// --- Empty state ---

function EmptyChart({ icon: Icon, message }: { icon: any; message: string }) {
  return (
    <div className="h-[240px] flex flex-col items-center justify-center gap-3 text-center">
      <div className="bg-muted/30 p-3 rounded-full">
        <Icon className="h-6 w-6 text-muted-foreground/40" />
      </div>
      <p className="text-xs text-muted-foreground/50 max-w-[200px] leading-relaxed">{message}</p>
    </div>
  )
}

// --- Skip Reasons Chart ---

const skipReasonsConfig = {
  count: { label: 'Jobs', color: 'var(--chart-5)' },
} satisfies ChartConfig

const SKIP_REASON_LABELS: Record<string, string> = {
  location_onsite: 'On-site Only',
  location_timezone: 'Timezone Mismatch',
  tech_gap: 'Tech Gap',
  seniority_mismatch: 'Seniority',
  growth_mismatch: 'Wrong Direction',
  none: 'No Single Reason',
}

export function SkipReasonsChart({ data }: { data: SkipReasonStat[] }) {
  const displayData = data
    .filter(item => item.reason !== 'none')
    .map(item => ({
      label: SKIP_REASON_LABELS[item.reason] || item.reason,
      count: item.count
    }))
  const hasData = displayData.length > 0 && displayData.some(d => d.count > 0)

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Why Jobs Were Skipped</CardTitle>
        <CardDescription className="text-xs">Primary disqualifier by category</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <ChartContainer config={skipReasonsConfig} className="h-[240px] w-full">
            <BarChart data={displayData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid horizontal={false} vertical={false} />
              <XAxis type="number" hide />
              <YAxis
                dataKey="label"
                type="category"
                tickLine={false}
                tickMargin={10}
                axisLine={false}
                className="text-[10px] font-medium"
                width={100}
              />
              <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
              <Bar dataKey="count" fill="var(--color-count)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ChartContainer>
        ) : (
          <EmptyChart icon={AlertCircle} message="Score some jobs to see why they're being skipped." />
        )}
      </CardContent>
    </Card>
  )
}

// --- Jobs by Country Chart ---

const countryConfig = {
  count: { label: 'Jobs', color: 'var(--chart-1)' },
} satisfies ChartConfig

export function CountryChart({ data }: { data: CountryStat[] }) {
  const displayData = data.slice(0, 8)
  const hasData = displayData.length > 0 && displayData.some(d => d.count > 0)

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Jobs by Country</CardTitle>
        <CardDescription className="text-xs">Geographic distribution of scored jobs</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <ChartContainer config={countryConfig} className="h-[240px] w-full">
            <BarChart data={displayData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid horizontal={false} vertical={false} />
              <XAxis type="number" hide />
              <YAxis
                dataKey="country"
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
          <EmptyChart icon={Globe} message="Score some jobs to see geographic distribution." />
        )}
      </CardContent>
    </Card>
  )
}

// --- Skills to Develop Chart ---

const missingSkillsConfig = {
  count: { label: 'Mentions', color: 'var(--chart-2)' },
} satisfies ChartConfig

export function MissingSkillsChart({ data }: { data: SkillCount[] }) {
  const displayData = data.slice(0, 10)
  const hasData = displayData.length > 0 && displayData.some(d => d.count > 0)

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Skills to Develop</CardTitle>
        <CardDescription className="text-xs">Required by jobs but not in your profile</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <ChartContainer config={missingSkillsConfig} className="h-[240px] w-full">
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
          <EmptyChart icon={Star} message="Score some jobs to see recurring skill gaps." />
        )}
      </CardContent>
    </Card>
  )
}
