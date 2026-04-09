import Link from 'next/link'
import type { components } from '@/lib/api/types'
import { ScoreRing } from '@/components/score/ScoreRing'
import { PriorityBadge } from '@/components/score/PriorityBadge'
import { MatchTierBadge } from '@/components/score/MatchTierBadge'
import { FitCategoryBadge } from '@/components/score/FitCategoryBadge'
import { timeAgo, getPlatformName } from '@/lib/utils/format'
import { Badge } from '@/components/ui/badge'
import { MapPin, Building2, ChevronRight, Banknote, HelpCircle } from 'lucide-react'
import { getCompanyQualitySignalLabel } from '@/lib/company-quality'

type JobResponse = components["schemas"]["JobResponse"]

const PRIORITY_BORDER: Record<string, string> = {
  high:   'border-l-green-500/70',
  medium: 'border-l-amber-500/60',
  low:    'border-l-slate-500/30',
  skip:   'border-l-red-500/40',
}

export function JobListItem({ job }: { job: JobResponse }) {
  const priority = job.score_breakdown?.apply_priority as string | undefined
  const fitCategory = job.score_breakdown?.fit_category as string | undefined
  const leftBorder = PRIORITY_BORDER[priority ?? ''] ?? 'border-l-border/30'
  const companySignals = Array.isArray(job.company_quality_signals) ? job.company_quality_signals.slice(0, 2) : []
  const isStrategicException = fitCategory === 'strategic_exception'

  return (
    <Link href={`/jobs/detail?id=${job.id}`}>
      <div className={`group relative flex items-center gap-6 p-4 rounded-xl border border-border/40 border-l-4 ${leftBorder} bg-card/30 hover:bg-card/60 hover:border-primary/30 transition-all duration-300 cursor-pointer shadow-sm backdrop-blur-sm`}>
        {/* Score Section */}
        <div className="flex-shrink-0 flex flex-col items-center gap-1 transition-transform group-hover:scale-105 duration-300">
          {job.is_sparse ? (
            <div className="w-[56px] h-[56px] rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500 shadow-inner">
              <HelpCircle className="h-6 w-6 stroke-[2.5]" />
            </div>
          ) : (
            <ScoreRing score={job.fit_score} size={56} strokeWidth={5} />
          )}
          {!job.is_sparse && <PriorityBadge priority={priority} />}
        </div>

        {/* Main Content */}
        <div className="flex-1 min-w-0 grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase font-mono tracking-widest text-muted-foreground/70 bg-muted/40 px-1.5 py-0.5 rounded">
                {getPlatformName(job.ats_platform)}
              </span>
              {job.status !== 'new' && (
                <div className="flex items-center gap-1.5">
                  <Badge variant="secondary" className="capitalize text-[10px] font-normal px-1.5 py-0 h-4 opacity-80">
                    {job.status}
                  </Badge>
                  {job.status === 'dismissed' && job.dismissal_reason && (
                    <Badge variant="outline" className="text-[10px] font-medium px-2 py-0 h-4 bg-muted/50 border-muted-foreground/20 text-muted-foreground">
                      {job.dismissal_reason}
                    </Badge>
                  )}
                </div>
              )}
              {job.match_tier && job.status !== 'dismissed' && (
                <div className="flex items-center gap-1.5">
                  <MatchTierBadge matchTier={job.match_tier} compact />
                </div>
              )}
              {job.is_sparse && (
                <Badge variant="outline" className="text-[9px] font-bold px-1.5 py-0 h-4 bg-amber-500/5 text-amber-600 dark:text-amber-500 border-amber-500/30 whitespace-nowrap">
                  ⚠️ Sparse Posting
                </Badge>
              )}
              {job.status !== 'dismissed' && <FitCategoryBadge fitCategory={fitCategory} compact />}
            </div>
            <h3 className="font-bold truncate text-lg group-hover:text-primary transition-colors leading-tight">
              {job.title}
            </h3>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1">
              <div className="flex items-center gap-1.5 text-sm text-foreground/80">
                <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="font-medium">{job.company_name}</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <MapPin className="h-3.5 w-3.5" />
                <span>{job.location}</span>
              </div>
              {job.salary && (
                <div className="flex items-center gap-1.5 text-xs text-green-600/80 dark:text-green-400/80 font-medium">
                  <Banknote className="h-3.5 w-3.5" />
                  <span>{job.salary}</span>
                </div>
              )}
            </div>
            {isStrategicException && companySignals.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {companySignals.map((signal: string) => (
                  <Badge
                    key={signal}
                    variant="outline"
                    className="text-[10px] font-medium px-2 py-0.5 h-auto bg-fuchsia-500/5 text-fuchsia-600 dark:text-fuchsia-400 border-fuchsia-500/20"
                  >
                    {getCompanyQualitySignalLabel(signal)}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Key Matches & Snippet */}
          <div className="hidden lg:flex flex-col gap-2 border-l border-border/40 pl-6">
            <div className="flex flex-wrap gap-1.5 overflow-hidden">
              {job.score_breakdown?.key_matches?.slice(0, 3).map((match: string) => (
                <Badge
                  key={match}
                  variant="outline"
                  className="bg-green-500/5 text-green-600 dark:text-green-400 border-green-500/20 text-[10px] font-medium py-0 h-5"
                >
                  {match}
                </Badge>
              ))}
              {(job.score_breakdown?.key_matches?.length ?? 0) > 3 && (
                <span className="text-[10px] text-muted-foreground self-center">
                  +{job.score_breakdown.key_matches.length - 3} more
                </span>
              )}
            </div>
            {job.score_reasoning && (
              <p className="text-xs text-muted-foreground/60 line-clamp-1 italic">
                "{job.score_reasoning}"
              </p>
            )}
          </div>
        </div>

        {/* Right Info Section */}
        <div className="flex-shrink-0 flex flex-col items-end gap-2 text-right">
          <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground/60">
            {timeAgo(job.first_seen_at)}
          </div>
          <div className="p-2 rounded-full bg-background/50 border border-border/50 text-muted-foreground group-hover:text-primary group-hover:border-primary/40 group-hover:bg-primary/5 transition-all">
            <ChevronRight className="h-4 w-4" />
          </div>
        </div>

        {/* Hover gradient */}
        <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      </div>
    </Link>
  )
}
