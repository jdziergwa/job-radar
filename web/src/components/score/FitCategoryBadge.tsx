import { Badge } from '@/components/ui/badge'
import { getFitCategoryClasses, getFitCategoryLabel } from '@/lib/fit-category'

export function FitCategoryBadge({ fitCategory }: { fitCategory?: string | null }) {
  const label = getFitCategoryLabel(fitCategory)
  if (!label) return null

  return (
    <Badge
      variant="outline"
      className={`px-2.5 py-0.5 h-auto font-semibold tracking-wide text-[10px] uppercase ${getFitCategoryClasses(fitCategory)}`}
    >
      {label}
    </Badge>
  )
}
