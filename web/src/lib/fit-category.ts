export type FitCategory =
  | 'core_fit'
  | 'adjacent_stretch'
  | 'conditional_fit'
  | 'strategic_exception'

function normalizeFitCategory(value?: string | null): FitCategory | '' {
  if (!value) return ''
  const normalized = value.trim().toLowerCase()
  if (
    normalized === 'core_fit' ||
    normalized === 'adjacent_stretch' ||
    normalized === 'conditional_fit' ||
    normalized === 'strategic_exception'
  ) {
    return normalized
  }
  return ''
}

export function getFitCategoryLabel(value?: string | null): string {
  const category = normalizeFitCategory(value)
  const labels: Record<FitCategory, string> = {
    core_fit: 'Core Fit',
    adjacent_stretch: 'Stretch Fit',
    conditional_fit: 'Conditional Fit',
    strategic_exception: 'Strategic Exception',
  }
  return category ? labels[category] : ''
}

export function getFitCategoryClasses(value?: string | null): string {
  const category = normalizeFitCategory(value)
  const classes: Record<FitCategory, string> = {
    core_fit: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    adjacent_stretch: 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20',
    conditional_fit: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    strategic_exception: 'bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-400 border-fuchsia-500/20',
  }
  return category ? classes[category] : ''
}

export function getFitCategoryExplanation(value?: string | null): string {
  const category = normalizeFitCategory(value)
  const explanations: Record<FitCategory, string> = {
    core_fit: 'This role aligns directly with your core role targets and seniority direction.',
    adjacent_stretch: 'This role sits in an adjacent direction but still has enough bridge evidence to stay viable.',
    conditional_fit: 'This role is acceptable only under explicit conditions from your scoring preferences.',
    strategic_exception: 'This role is below your default seniority target but remains viable because explicit company-quality signals matched your strategic preferences.',
  }
  return category ? explanations[category] : ''
}
