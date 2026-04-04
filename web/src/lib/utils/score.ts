export type ScoreTier = 'high' | 'medium' | 'low' | 'unscored'

export function getScoreTier(score: number | null | undefined): ScoreTier {
  if (score === null || score === undefined) return 'unscored'
  if (score >= 80) return 'high'
  if (score >= 60) return 'medium'
  return 'low'
}

export function scoreToColor(score: number | null | undefined): string {
  const tier = getScoreTier(score)
  return { high: '#22c55e', medium: '#f59e0b', low: '#ef4444', unscored: '#6b7280' }[tier]
}

export function priorityToClasses(priority: string): string {
  const map: Record<string, string> = {
    high:   'bg-violet-500/15 text-violet-400 border border-violet-500/30',
    medium: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
    low:    'bg-slate-500/15 text-slate-400 border border-slate-500/30',
    skip:   'bg-red-500/15 text-red-400 border border-red-500/30',
  }
  return map[priority] ?? map.low
}

export function getMatchQualityLabel(priority: string | undefined): string {
  if (!priority) return 'Not Scored'
  const map: Record<string, string> = {
    high:   'Strong Match',
    medium: 'Good Match',
    low:    'Weak Match',
    skip:   'Low Fit',
  }
  return map[priority] ?? 'Strong Match'
}
