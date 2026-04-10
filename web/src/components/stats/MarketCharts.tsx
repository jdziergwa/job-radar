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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AlertCircle, Globe, Star, BarChart3, Banknote } from 'lucide-react'
import { SkipReasonStat, CountryStat, SkillCount, SalaryStat } from '@/lib/api/types'

// --- Empty state ---

const MIN_VERTICAL_CHART_HEIGHT = 240
const VERTICAL_CHART_ROW_HEIGHT = 32
const MAX_MISSING_SKILL_LABEL_LENGTH = 18
const MAX_SALARY_LABEL_LENGTH = 16

function getVerticalChartHeight(itemCount: number) {
  return Math.max(MIN_VERTICAL_CHART_HEIGHT, itemCount * VERTICAL_CHART_ROW_HEIGHT)
}

function truncateLabel(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value
  }

  return `${value.slice(0, maxLength - 1).trimEnd()}…`
}

function MissingSkillsTick({ x, y, payload }: any) {
  const fullLabel = typeof payload?.value === 'string' ? payload.value : ''
  const truncatedLabel = truncateLabel(fullLabel, MAX_MISSING_SKILL_LABEL_LENGTH)

  return (
    <g transform={`translate(${x},${y})`}>
      <title>{fullLabel}</title>
      <text
        x={0}
        y={0}
        dy={4}
        textAnchor="end"
        className="fill-muted-foreground text-[10px] font-medium"
      >
        {truncatedLabel}
      </text>
    </g>
  )
}

function SalaryTick({ x, y, payload }: any) {
  const fullLabel = typeof payload?.value === 'string' ? payload.value : ''
  const truncatedLabel = truncateLabel(fullLabel, MAX_SALARY_LABEL_LENGTH)

  return (
    <g transform={`translate(${x},${y})`}>
      <title>{fullLabel}</title>
      <text
        x={0}
        y={0}
        dy={4}
        textAnchor="end"
        className="fill-muted-foreground text-[10px] font-medium"
      >
        {truncatedLabel}
      </text>
    </g>
  )
}

type SalaryBarDatum = {
  label: string
  count: number
}

function SalaryBars({ data, viewportHeight = 240 }: { data: SalaryBarDatum[]; viewportHeight?: number }) {
  const chartHeight = getVerticalChartHeight(data.length)

  return (
    <div className="overflow-y-auto pr-2" style={{ height: viewportHeight }}>
      <ChartContainer config={salaryConfig} className="w-full" style={{ height: chartHeight }}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 12 }}>
          <CartesianGrid horizontal={false} vertical={false} />
          <XAxis type="number" hide />
          <YAxis
            dataKey="label"
            type="category"
            tickLine={false}
            tickMargin={10}
            axisLine={false}
            width={110}
            tick={<SalaryTick />}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                hideIndicator
                labelFormatter={(_: unknown, payload: any[]) => payload?.[0]?.payload?.label ?? ''}
              />
            }
          />
          <Bar dataKey="count" fill="var(--color-count)" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ChartContainer>
    </div>
  )
}

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
  const chartHeight = getVerticalChartHeight(displayData.length)

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Skills to Develop</CardTitle>
        <CardDescription className="text-xs">Required by jobs but not in your profile</CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          <div className="h-[240px] overflow-y-auto pr-2">
            <ChartContainer config={missingSkillsConfig} className="w-full" style={{ height: chartHeight }}>
              <BarChart data={displayData} layout="vertical" margin={{ left: 8, right: 12 }}>
                <CartesianGrid horizontal={false} vertical={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey="skill"
                  type="category"
                  tickLine={false}
                  tickMargin={10}
                  axisLine={false}
                  width={118}
                  tick={<MissingSkillsTick />}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      hideIndicator
                      labelFormatter={(_: unknown, payload: any[]) => payload?.[0]?.payload?.skill ?? ''}
                    />
                  }
                />
                <Bar dataKey="count" fill="var(--color-count)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ChartContainer>
          </div>
        ) : (
          <EmptyChart icon={Star} message="Score some jobs to see recurring skill gaps." />
        )}
      </CardContent>
    </Card>
  )
}
// --- Salary Distribution Chart ---

const salaryConfig = {
  count: { label: 'Jobs', color: 'var(--chart-4)' },
} satisfies ChartConfig

export function SalaryChart({ data }: { data: SalaryStat[] }) {
  const normalizedData = data.filter(item => item.count > 0)
  const hasData = normalizedData.length > 0

  const undisclosedCount = data
    .filter(item => item.range === 'Undisclosed')
    .reduce((sum, item) => sum + item.count, 0)
  const totalWithData = data.reduce((sum, d) => sum + d.count, 0)
  const undisclosedPercent = totalWithData > 0 ? (undisclosedCount / totalWithData) * 100 : 0
  const disclosedPercent = (100 - undisclosedPercent).toFixed(1)
  const currencies = Array.from(
    new Set(
      data
        .filter(item => item.range !== 'Undisclosed' && item.currency)
        .map(item => item.currency as string)
    )
  )
  const hasCurrencyTabs = currencies.length > 1
  const salaryViewportHeight = hasCurrencyTabs ? 184 : 240
  const allTabData = [
    ...currencies.map(currency => ({
      label: currency,
      count: data
        .filter(item => item.range !== 'Undisclosed' && item.currency === currency)
        .reduce((sum, item) => sum + item.count, 0),
    })),
    ...(undisclosedCount > 0 ? [{ label: 'Undisclosed', count: undisclosedCount }] : []),
  ].filter(item => item.count > 0)
  const byCurrencyData = new Map(
    currencies.map(currency => [
      currency,
      normalizedData
        .filter(item => item.range !== 'Undisclosed' && item.currency === currency)
        .map(item => ({
          label: item.range,
          count: item.count,
        })),
    ])
  )

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Salary Distribution</CardTitle>
        <CardDescription className="text-xs">
          {disclosedPercent}% of analyzed postings include compensation
          {currencies.length > 0 ? '; tabs are per native currency.' : '.'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {hasData ? (
          hasCurrencyTabs ? (
            <Tabs defaultValue="all" className="w-full">
              <div className="mb-4 overflow-x-auto pb-1">
                <TabsList className="h-10 min-w-max flex-nowrap justify-start gap-1 bg-muted/30 p-1 border border-border/50">
                  <TabsTrigger value="all" className="px-3 text-xs">All</TabsTrigger>
                  {currencies.map(currency => (
                    <TabsTrigger key={currency} value={currency} className="px-3 text-xs">
                      {currency}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </div>

              <TabsContent value="all" className="mt-0 animate-in fade-in slide-in-from-top-2 duration-300">
                <SalaryBars data={allTabData} viewportHeight={salaryViewportHeight} />
              </TabsContent>

              {currencies.map(currency => (
                <TabsContent
                  key={currency}
                  value={currency}
                  className="mt-0 animate-in fade-in slide-in-from-top-2 duration-300"
                >
                  <SalaryBars data={byCurrencyData.get(currency) || []} viewportHeight={salaryViewportHeight} />
                </TabsContent>
              ))}
            </Tabs>
          ) : (
            <SalaryBars
              data={
                currencies.length === 1
                  ? byCurrencyData.get(currencies[0]) || []
                  : allTabData
              }
            />
          )
        ) : (
          <EmptyChart icon={Banknote} message="Score jobs with salary info to see market benchmarks." />
        )}
      </CardContent>
    </Card>
  )
}
