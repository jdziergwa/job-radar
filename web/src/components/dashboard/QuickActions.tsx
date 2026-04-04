'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Database, ShieldCheck, Activity } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { PipelineTrigger } from '@/components/pipeline/PipelineTrigger'
import { RescoreAllButton } from '@/components/jobs/RescoreAllButton'

export function QuickActions() {
  const [health, setHealth] = useState<{ status: string; version: string } | null>(null)
  const [profiles, setProfiles] = useState<{ name: string }[]>([])

  useEffect(() => {
    api.GET('/api/health').then(({ data }) => {
      if (data) setHealth(data as any)
    }).catch(() => {})

    api.GET('/api/profiles').then(({ data }) => {
      if (data) setProfiles(data as any)
    }).catch(() => {})
  }, [])

  const isHealthy = health?.status === 'ok'

  return (
    <div className="space-y-6">
      <Card className="md:hidden border-border/50 bg-background/30 backdrop-blur-md shadow-sm overflow-hidden relative group">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
        <CardHeader className="pb-3 relative">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            Quick Actions
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 relative">
          <div className="flex flex-col gap-3">
            <PipelineTrigger />
            <RescoreAllButton variant="secondary" className="w-full justify-start border-border/40" />
          </div>
          <p className="text-[10px] text-muted-foreground px-1 leading-relaxed">
            Trigger a manual sync of all job boards or force a fresh AI re-evaluation of all current jobs.
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/50 bg-background/30 backdrop-blur-md shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-500" />
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Database className="h-3.5 w-3.5" />
              <span>Database</span>
            </div>
            <Badge
              variant="outline"
              className={`text-[10px] py-0 border ${
                health === null
                  ? 'text-muted-foreground border-muted/30'
                  : isHealthy
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                  : 'bg-destructive/10 text-destructive border-destructive/20'
              }`}
            >
              {health === null ? 'Checking...' : isHealthy ? 'Healthy' : 'Error'}
            </Badge>
          </div>

          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>API</span>
            </div>
            <Badge
              variant="outline"
              className={`text-[10px] py-0 border ${
                health === null
                  ? 'text-muted-foreground border-muted/30'
                  : isHealthy
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                  : 'bg-destructive/10 text-destructive border-destructive/20'
              }`}
            >
              {health === null ? '...' : isHealthy ? `v${health.version}` : 'Offline'}
            </Badge>
          </div>

          <div className="pt-2 border-t border-border/30">
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase font-mono text-muted-foreground tracking-wider">Active Profiles</span>
              <div className="flex flex-wrap gap-1">
                {profiles.length === 0 ? (
                  <span className="text-[10px] text-muted-foreground italic">None found</span>
                ) : (
                  profiles.map((p) => (
                    <Badge key={p.name} variant="secondary" className="text-[10px] font-normal py-0">
                      {p.name}
                    </Badge>
                  ))
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
