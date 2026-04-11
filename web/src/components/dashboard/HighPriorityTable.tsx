import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { ScoreRing } from '@/components/score/ScoreRing'
import { timeAgo } from '@/lib/utils/format'
import { Building2, ExternalLink, MapPin } from 'lucide-react'

export function HighPriorityTable({ jobs, loading }: { jobs: any[], loading?: boolean }) {
  if (loading) {
    return (
      <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-border/50 bg-background/30 shadow-sm backdrop-blur-md">
        <div className="border-b border-border/50 bg-muted/20 p-4">
          <div className="h-5 w-40 animate-pulse rounded bg-muted" />
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-xl border border-border/40 bg-background/45 p-3">
              <div className="mb-2 h-4 w-24 animate-pulse rounded bg-muted" />
              <div className="mb-2 h-5 w-4/5 animate-pulse rounded bg-muted" />
              <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-border/50 bg-background/30 shadow-sm backdrop-blur-md">
      <div className="flex items-center justify-between gap-3 border-b border-border/50 bg-muted/20 p-4">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-sm tracking-tight text-foreground/90">High Priority Opportunities</h3>
          <Badge variant="outline" className="border-border/50 bg-background/50 text-[10px] font-semibold uppercase tracking-wider">
            {jobs.length} shown
          </Badge>
        </div>
        <Link href="/jobs?status=scored&min_score=80" className="text-xs text-primary hover:underline font-medium flex items-center gap-1">
          View all <ExternalLink className="h-3 w-3" />
        </Link>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {jobs.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border/50 bg-muted/10 px-4 text-center text-sm text-muted-foreground">
            No high-priority jobs found.
          </div>
        ) : (
          jobs.map((job, index) => (
            <Link href={`/job?id=${job.id}`} key={job.id} className="block">
              <div className="rounded-xl border border-border/40 bg-background/45 p-3 shadow-sm transition-colors hover:border-primary/30 hover:bg-primary/5">
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/65">
                        #{index + 1}
                      </span>
                      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/65">
                        {timeAgo(job.first_seen_at)}
                      </span>
                    </div>

                    <h4 className="line-clamp-2 text-sm font-bold leading-tight text-foreground">
                      {job.title}
                    </h4>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Building2 className="h-3 w-3" />
                        <span className="truncate max-w-[140px]">{job.company_name}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        <span className="truncate max-w-[140px]">{job.location}</span>
                      </div>
                    </div>
                  </div>
                  <div className="shrink-0">
                    <ScoreRing score={job.fit_score ?? null} size={34} strokeWidth={4} />
                  </div>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
