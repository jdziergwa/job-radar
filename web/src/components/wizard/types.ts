import { components } from "@/lib/api/types"

export type CVAnalysis = components["schemas"]["CVAnalysisResponse"]
export type UserPreferences = components["schemas"]["UserPreferences"] & {
  baseCity?: string
  baseCountry?: string
  careerDirectionEdited?: boolean
  companyQualitySignals?: string[]
  allowLowerSeniorityAtStrategicCompanies?: boolean
  goodMatchSignalsConfirmed?: boolean
  dealBreakersConfirmed?: boolean
}

export const DEFAULT_TIMEZONE_PREF = 'overlap_strict'

export function normalizeTimezonePref(value?: string): string {
  if (!value || value === 'local') return DEFAULT_TIMEZONE_PREF
  return value
}

export interface WizardData {
  wizardFlowMode?: 'onboarding' | 'edit_preferences' | 'update_cv'
  canGoBack?: boolean
  originalCvAnalysis?: CVAnalysis
  originalUserPreferences?: Partial<UserPreferences>
  path?: 'manual' | 'ai'
  cvFile?: { name: string, size: number }
  cvAnalysis?: CVAnalysis
  analysisPromise?: Promise<any>
  targetRoles?: string[]
  seniority?: string[]
  baseCity?: string
  baseCountry?: string
  location?: string
  workAuth?: string
  remotePref?: string[]
  primaryRemotePref?: string
  timezonePref?: string
  targetRegions?: string[]
  excludedRegions?: string[]
  careerDirection?: string
  careerGoal?: 'stay' | 'pivot' | 'step_up' | 'broaden'
  careerDirectionEdited?: boolean
  enableStandardExclusions?: boolean
  industries?: string[]
  goodMatchSignals?: string[]
  goodMatchSignalsConfirmed?: boolean
  companyQualitySignals?: string[]
  allowLowerSeniorityAtStrategicCompanies?: boolean
  dealBreakers?: string[]
  dealBreakersConfirmed?: boolean
  additionalContext?: string
  completed?: boolean
  error?: string
  retry?: boolean
}

export interface StepProps {
  onNext: (data?: Partial<WizardData>) => void
  onBack: (data?: Partial<WizardData>) => void
  onUpdate: (data: Partial<WizardData>) => void
  data: Partial<WizardData>
}
