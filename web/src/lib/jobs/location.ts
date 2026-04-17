type LocationLike = {
  location?: string | null
  workplace_type?: string | null
  raw_location?: string | null
}

export function formatJobLocation(job: LocationLike): string {
  const workplaceType = (job.workplace_type || '').trim()
  const rawLocation = (job.raw_location || '').trim()
  const location = (job.location || '').trim()

  const baseLocation = rawLocation || location
  if (workplaceType && baseLocation) {
    if (workplaceType.toLowerCase() === baseLocation.toLowerCase()) {
      return baseLocation
    }
    return `${workplaceType} • ${baseLocation}`
  }

  return workplaceType || baseLocation || 'Location Unspecified'
}
