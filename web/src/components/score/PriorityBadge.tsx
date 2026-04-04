import { Badge } from '@/components/ui/badge'
import { priorityToClasses } from '@/lib/utils/score'

export function PriorityBadge({ priority }: { priority: string | undefined }) {
  if (!priority) return null
  
  return (
    <Badge 
      variant="outline" 
      className={`uppercase text-[10px] tracking-wider font-semibold py-0.5 px-2 rounded-full border-none shadow-sm ${priorityToClasses(priority)}`}
    >
      {priority}
    </Badge>
  )
}
