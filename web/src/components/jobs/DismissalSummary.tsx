'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertCircle, MapPin, Tag, Type } from 'lucide-react'

export function DismissalSummary() {
  const [stats, setStats] = useState<{ reasons: Record<string, number>; total: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.GET('/api/stats/dismissed', { params: { query: { profile: 'default' } } }).then(({ data }) => {
      if (data) setStats(data as any)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading || !stats || stats.total === 0) return null

  // Sort reasons by count
  const sortedReasons = Object.entries(stats.reasons)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 4)

  const getIcon = (reason: string) => {
    if (reason.toLowerCase().includes('title')) return <Type className="h-3 w-3" />
    if (reason.toLowerCase().includes('location')) return <MapPin className="h-3 w-3" />
    if (reason.toLowerCase().includes('signals') || reason.toLowerCase().includes('keywords')) return <Tag className="h-3 w-3" />
    return <AlertCircle className="h-3 w-3" />
  }

  const getColor = (reason: string) => {
    if (reason.toLowerCase().includes('title')) return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
    if (reason.toLowerCase().includes('location')) return 'bg-amber-500/10 text-amber-500 border-amber-500/20'
    if (reason.toLowerCase().includes('signals')) return 'bg-purple-500/10 text-purple-500 border-purple-500/20'
    return 'bg-muted/50 text-muted-foreground border-border/50'
  }

  return (
    <Card className="mb-6 border-primary/20 bg-primary/5 backdrop-blur-sm overflow-hidden animate-in fade-in slide-in-from-top-2 duration-500">
      <CardContent className="p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold flex items-center gap-2 mb-1">
              <AlertCircle className="h-4 w-4 text-primary" />
              Dismissal Audit Summary
            </h3>
            <p className="text-xs text-muted-foreground">
              Breakdown of why {stats.total} jobs were recently filtered out.
            </p>
          </div>
          
          <div className="flex flex-wrap gap-2">
            {sortedReasons.map(([reason, count]) => {
              const percentage = Math.round((count / stats.total) * 100)
              return (
                <div 
                  key={reason}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[10px] font-medium transition-all ${getColor(reason)}`}
                >
                  {getIcon(reason)}
                  <span className="truncate max-w-[120px]">{reason}</span>
                  <span className="font-bold opacity-80">{percentage}%</span>
                </div>
              )
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
