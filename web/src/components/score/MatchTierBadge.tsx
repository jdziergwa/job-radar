import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

function getMatchTierLabel(matchTier?: string | null): string {
  if (!matchTier) return ''

  const normalized = matchTier.trim().toLowerCase()
  if (normalized === 'high_confidence') return 'Direct Match'
  if (normalized === 'signal_match' || normalized === 'broad_match') return 'Signal Match'

  return normalized.replace(/_/g, ' ')
}

function getMatchTierExplanation(matchTier?: string | null): string {
  if (!matchTier) return ''

  const normalized = matchTier.trim().toLowerCase()
  if (normalized === 'high_confidence') {
    return 'The role matched your target signals directly, with strong evidence from title, stack, and seniority.'
  }
  if (normalized === 'signal_match' || normalized === 'broad_match') {
    return 'The role was surfaced through supporting signals rather than a direct title match, so it may be relevant but needs a quick sanity check.'
  }

  return `Match tier: ${getMatchTierLabel(matchTier)}`
}

function getMatchTierClasses(matchTier?: string | null): string {
  const normalized = matchTier?.trim().toLowerCase()
  if (normalized === 'high_confidence') {
    return 'bg-indigo-500/12 text-indigo-600 dark:text-indigo-400 border-indigo-500/20'
  }
  if (normalized === 'signal_match' || normalized === 'broad_match') {
    return 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20'
  }

  return 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20'
}

type MatchTierBadgeProps = {
  matchTier?: string | null
  compact?: boolean
}

export function MatchTierBadge({ matchTier, compact = false }: MatchTierBadgeProps) {
  const label = getMatchTierLabel(matchTier)
  const explanation = getMatchTierExplanation(matchTier)

  if (!label) return null

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Badge
            variant="outline"
            className={`cursor-help border text-[10px] font-semibold uppercase tracking-wide whitespace-nowrap ${compact ? 'h-4 px-1.5 py-0 text-[9px]' : 'h-auto px-2.5 py-0.5'} ${getMatchTierClasses(matchTier)}`}
          />
        }
      >
        {label}
      </TooltipTrigger>
      <TooltipContent className="max-w-64 text-[11px] leading-relaxed">
        {explanation}
      </TooltipContent>
    </Tooltip>
  )
}
