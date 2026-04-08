export interface CompanyQualitySignalOption {
  value: string
  label: string
}

export const COMPANY_QUALITY_SIGNAL_OPTIONS: CompanyQualitySignalOption[] = [
  { value: 'notable brand', label: 'Notable Brand' },
  { value: 'strong product company', label: 'Strong Product Company' },
  { value: 'strong cv value', label: 'Strong CV Value' },
  { value: 'high engineering reputation', label: 'High Engineering Reputation' },
]

export function normalizeCompanyQualitySignal(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, ' ')
}

export function dedupeCompanyQualitySignals(values: string[]): string[] {
  const seen = new Set<string>()
  const cleaned: string[] = []

  for (const value of values) {
    const normalized = normalizeCompanyQualitySignal(value)
    if (!normalized || seen.has(normalized)) continue
    cleaned.push(normalized)
    seen.add(normalized)
  }

  return cleaned
}

export function getCompanyQualitySignalLabel(value: string): string {
  const normalized = normalizeCompanyQualitySignal(value)
  const option = COMPANY_QUALITY_SIGNAL_OPTIONS.find((item) => item.value === normalized)
  if (option) return option.label
  return normalized.replace(/\b\w/g, (char) => char.toUpperCase())
}
