import Link from 'next/link'
import { ScoreRing } from '@/components/score/ScoreRing'
import { timeAgo } from '@/lib/utils/format'
import { Badge } from '@/components/ui/badge'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Building2, MapPin, ExternalLink } from 'lucide-react'

export function HighPriorityTable({ jobs, loading }: { jobs: any[], loading?: boolean }) {
  if (loading) {
    return (
      <div className="rounded-xl border border-border/50 bg-background/30 backdrop-blur-md overflow-hidden">
        <div className="p-4 border-b border-border/50">
          <div className="h-5 w-32 animate-pulse rounded bg-muted" />
        </div>
        <div className="p-6 space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="h-10 w-10 animate-pulse rounded-full bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
                <div className="h-3 w-1/4 animate-pulse rounded bg-muted" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border/50 bg-background/30 backdrop-blur-md overflow-hidden shadow-sm">
      <div className="p-4 border-b border-border/50 flex justify-between items-center bg-muted/20">
        <h3 className="font-semibold text-sm tracking-tight text-foreground/90">High Priority Opportunities</h3>
        <Link href="/jobs" className="text-xs text-primary hover:underline font-medium flex items-center gap-1">
          View all <ExternalLink className="h-3 w-3" />
        </Link>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/40">
              <TableHead className="w-[400px]">Job Role</TableHead>
              <TableHead className="text-center">Score</TableHead>
              <TableHead className="text-right">Added</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {jobs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="h-32 text-center text-muted-foreground">
                  No high-priority jobs found.
                </TableCell>
              </TableRow>
            ) : (
              jobs.map((job) => (
                <TableRow key={job.id} className="group hover:bg-primary/5 transition-colors border-border/30">
                  <TableCell>
                    <Link href={`/job?id=${job.id}`} className="block">
                      <div className="flex flex-col gap-0.5">
                        <span className="font-bold text-foreground group-hover:text-primary transition-colors truncate max-w-[320px]">
                          {job.title}
                        </span>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Building2 className="h-3 w-3" />
                            <span className="truncate max-w-[120px]">{job.company_name}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <MapPin className="h-3 w-3" />
                            <span className="truncate max-w-[120px]">{job.location}</span>
                          </div>
                        </div>
                      </div>
                    </Link>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex justify-center">
                       <ScoreRing score={job.fit_score} size={36} strokeWidth={4} />
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-[10px] text-muted-foreground uppercase whitespace-nowrap">
                    {timeAgo(job.first_seen_at)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
