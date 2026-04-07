import { components } from "@/lib/api/types"

export type CVAnalysis = components["schemas"]["CVAnalysisResponse"]
export type UserPreferences = components["schemas"]["UserPreferences"]

export interface WizardData {
  path?: 'manual' | 'ai'
  cvFile?: { name: string, size: number }
  cvAnalysis?: CVAnalysis
  analysisPromise?: Promise<any>
  targetRoles?: string[]
  seniority?: string[]
  location?: string
  workAuth?: string
  remotePref?: string[]
  primaryRemotePref?: string
  timezonePref?: string
  targetRegions?: string[]
  excludedRegions?: string[]
  careerDirection?: string
  industries?: string[]
  goodMatchSignals?: string[]
  dealBreakers?: string[]
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
