import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { getFitCategoryClasses, getFitCategoryExplanation, getFitCategoryLabel } from '@/lib/fit-category'

type FitCategoryBadgeProps = {
  fitCategory?: string | null
  compact?: boolean
}

export function FitCategoryBadge({ fitCategory, compact = false }: FitCategoryBadgeProps) {
  const label = getFitCategoryLabel(fitCategory)
  const explanation = getFitCategoryExplanation(fitCategory)
  if (!label) return null

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Badge
            variant="outline"
            className={`cursor-help font-semibold uppercase tracking-wide whitespace-nowrap ${compact ? 'h-4 px-1.5 py-0 text-[9px]' : 'h-auto px-2.5 py-0.5 text-[10px]'} ${getFitCategoryClasses(fitCategory)}`}
          />
        }
      >
        {label}
      </TooltipTrigger>
      {explanation && (
        <TooltipContent className="max-w-64 text-[11px] leading-relaxed">
          {explanation}
        </TooltipContent>
      )}
    </Tooltip>
  )
}
