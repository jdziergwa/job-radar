export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

export function timeAgo(iso: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diff / 86_400_000)
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  return `${Math.floor(days / 30)}mo ago`
}


export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '—'
  return `${score}`
}

export function getPlatformName(slug: string): string {
  const mapping: Record<string, string> = {
    'remotive': 'Remotive',
    'remoteok': 'Remote OK',
    'greenhouse': 'Greenhouse',
    'lever': 'Lever',
    'ashby': 'Ashby',
    'workable': 'Workable',
    'aggregator': 'Aggregator',
  }
  return mapping[slug.toLowerCase()] || slug.charAt(0).toUpperCase() + slug.slice(1)
}
