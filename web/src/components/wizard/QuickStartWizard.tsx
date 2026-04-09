'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { WizardStepper } from './WizardStepper'
import { ChoosePath } from './steps/ChoosePath'
import { UploadCV } from './steps/UploadCV'
import { AIAnalysis } from './steps/AIAnalysis'
import { ReviewProfile } from './steps/ReviewProfile'
import { SearchLocation } from './steps/SearchLocation'
import { PreferencesGoals } from './steps/PreferencesGoals'
import { ReviewGenerate } from './steps/ReviewGenerate'
import { Done } from './steps/Done'
import { Radar, X, SlidersHorizontal, FileUp } from 'lucide-react'
import { api } from '@/lib/api/client'
import { toast } from 'sonner'
import { WizardData } from './types'

const STEPS = [
  "Get Started",
  "Upload CV",
  "Analyzing",
  "Review Profile",
  "Search & Location",
  "Preferences",
  "Preview",
  "Done"
]

interface QuickStartWizardProps {
  onComplete: () => void
  initialData?: Partial<WizardData>
  initialStep?: number
  storageKey?: string
  onExit?: () => void
  mode?: 'onboarding' | 'edit_preferences' | 'update_cv'
  embedded?: boolean
}

export function QuickStartWizard({
  onComplete,
  initialData,
  initialStep = 0,
  storageKey = 'job-radar-wizard-state',
  onExit,
  mode = 'onboarding',
  embedded = false,
}: QuickStartWizardProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [wizardData, setWizardData] = useState<Partial<WizardData>>({})
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [isInitialized, setIsInitialized] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const shouldPersistDraft = mode === 'onboarding' && !embedded
  const minimumStep = mode === 'edit_preferences' ? 4 : mode === 'update_cv' ? 1 : 0

  // Reset scroll on step change
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({ top: 0, behavior: 'instant' })
    }
  }, [currentStep])

  // Load saved onboarding draft, or initialize from provided state for guided edit flows.
  useEffect(() => {
    if (!shouldPersistDraft) {
      localStorage.removeItem(storageKey)
      setCurrentStep(initialStep)
      setWizardData({ wizardFlowMode: mode, ...(initialData || {}) })
      setCompletedSteps(initialStep > 0 ? Array.from({ length: initialStep }, (_, idx) => idx) : [])
      setIsInitialized(true)
      return
    }

    const saved = localStorage.getItem(storageKey)
    if (saved) {
      try {
        const { currentStep: savedStep, wizardData: savedData, completedSteps: savedCompleted } = JSON.parse(saved)
        setCurrentStep(savedStep || 0)
        setWizardData(savedData || { wizardFlowMode: mode })
        setCompletedSteps(savedCompleted || [])
      } catch (err) {
        console.error("Failed to restore wizard state", err)
      }
    } else {
      setCurrentStep(initialStep)
      setWizardData({ wizardFlowMode: mode, ...(initialData || {}) })
      setCompletedSteps(initialStep > 0 ? Array.from({ length: initialStep }, (_, idx) => idx) : [])
    }
    setIsInitialized(true)
  }, [initialData, initialStep, mode, shouldPersistDraft, storageKey])

  // Persist onboarding drafts only. Settings-driven guided edits should always reopen from saved server state.
  useEffect(() => {
    if (!isInitialized || !shouldPersistDraft) return
    
    // Exclude non-serializable fields like Promises and Files
    const { analysisPromise, ...serializableData } = wizardData
    
    localStorage.setItem(storageKey, JSON.stringify({
      currentStep,
      wizardData: serializableData,
      completedSteps
    }))
  }, [currentStep, wizardData, completedSteps, isInitialized, shouldPersistDraft, storageKey])

  const handleUpdate = useCallback((stepData: Partial<WizardData>) => {
    setWizardData((prev) => ({ ...prev, ...stepData }))
  }, [])

  const handleNext = useCallback(async (stepData?: Partial<WizardData>) => {
    // Handle manual path branch
    if (stepData?.path === 'manual') {
      setWizardData((prev) => ({ ...prev, path: 'manual' }))
      // Reset completed steps to only include the first step
      setCompletedSteps([0])
      setCurrentStep(6) // Review & Generate step
      return
    }

    let updatedData = wizardData
    if (stepData) {
      updatedData = { ...wizardData, ...stepData }
      setWizardData(updatedData)
    }

    // Clear manual path if we're moving from step 0 to step 1 (AI path)
    if (currentStep === 0 && !stepData?.path) {
      setWizardData((prev) => {
        const { path, ...rest } = prev
        return rest
      })
      setCompletedSteps([0])
    }

    setCompletedSteps((prev) => [...new Set([...prev, currentStep])])
    
    if (currentStep === STEPS.length - 1) {
      if (shouldPersistDraft) {
        localStorage.removeItem(storageKey)
      }
      onComplete()
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }, [currentStep, onComplete, shouldPersistDraft, storageKey, wizardData])

  const handleBack = useCallback((backData?: Partial<WizardData>) => {
    let nextStep = currentStep > minimumStep ? currentStep - 1 : minimumStep
    
    if (backData) {
      setWizardData((prev) => ({ ...prev, ...backData }))
      
      // If we're resetting CV data, jump back to Step 1 (Upload CV)
      if (backData.cvFile === undefined && backData.cvAnalysis === undefined) {
        nextStep = mode === 'edit_preferences' ? minimumStep : 1
        setCompletedSteps(mode === 'edit_preferences' ? Array.from({ length: minimumStep }, (_, idx) => idx) : [0])
      }
    }
    
    if (currentStep > minimumStep) {
      if (wizardData?.path === 'manual' && currentStep === 6) {
        setCurrentStep(minimumStep)
      } else {
        setCurrentStep(nextStep)
      }
    }
  }, [currentStep, minimumStep, mode, wizardData?.path])

  const renderStep = () => {
    const props = {
      onNext: handleNext,
      onBack: handleBack,
      onUpdate: handleUpdate,
      data: { ...wizardData, canGoBack: currentStep > minimumStep }
    }

    switch (currentStep) {
      case 0: return <ChoosePath {...props} />
      case 1: return <UploadCV {...props} />
      case 2: return <AIAnalysis {...props} />
      case 3: return <ReviewProfile {...props} />
      case 4: return <SearchLocation {...props} />
      case 5: return <PreferencesGoals {...props} />
      case 6: return <ReviewGenerate {...props} />
      case 7: return <Done {...props} />
      default: return null
    }
  }

  const flowMode = wizardData.wizardFlowMode || mode
  const isEditFlow = flowMode === 'edit_preferences' || flowMode === 'update_cv'

  const stepperConfig = (() => {
    if (wizardData?.path === 'manual') {
      return {
        steps: [STEPS[0], STEPS[6], STEPS[7]],
        currentStep: currentStep === 0 ? 0 : currentStep === 6 ? 1 : 2,
        completedSteps: completedSteps.map(idx => (idx === 0 ? 0 : idx === 6 ? 1 : idx === 7 ? 2 : -1)).filter(idx => idx !== -1),
      }
    }
    if (flowMode === 'edit_preferences') {
      const steps = ['Location', 'Preferences', 'Preview', 'Done']
      const stepMap: Record<number, number> = { 4: 0, 5: 1, 6: 2, 7: 3 }
      return {
        steps,
        currentStep: stepMap[currentStep] ?? 0,
        completedSteps: completedSteps.map(idx => stepMap[idx]).filter((idx): idx is number => idx !== undefined),
      }
    }
    if (flowMode === 'update_cv') {
      const steps = ['Upload CV', 'Analyzing', 'Profile', 'Location', 'Preferences', 'Preview', 'Done']
      const stepMap: Record<number, number> = { 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6 }
      return {
        steps,
        currentStep: stepMap[currentStep] ?? 0,
        completedSteps: completedSteps.map(idx => stepMap[idx]).filter((idx): idx is number => idx !== undefined),
      }
    }
    return {
      steps: STEPS,
      currentStep,
      completedSteps,
    }
  })()

  const shellCopy = (() => {
    if (flowMode === 'edit_preferences') {
      return {
        kicker: 'Settings',
        title: 'Edit Preferences',
        subtitle: 'Adjust your saved preferences and regenerate your profile before applying updates.',
        icon: SlidersHorizontal,
      }
    }
    if (flowMode === 'update_cv') {
      return {
        kicker: 'Settings',
        title: 'Start Fresh',
        subtitle: 'Upload a CV and rebuild your guided profile from the beginning.',
        icon: FileUp,
      }
    }
    return {
      kicker: 'Onboarding Wizard',
      title: 'Job Radar',
      subtitle: null,
      icon: Radar,
    }
  })()
  const ShellIcon = shellCopy.icon
  const progressCurrent = stepperConfig.currentStep + 1
  const progressTotal = stepperConfig.steps.length
  const progressPercent = progressTotal > 0 ? (progressCurrent / progressTotal) * 100 : 100

  return (
    <div 
      ref={scrollContainerRef}
      className={
        isEditFlow
          ? embedded
            ? "flex w-full flex-col justify-start bg-transparent overflow-y-auto scroll-smooth"
            : "flex w-full flex-col items-center justify-start bg-background/20 px-2 py-2 overflow-y-auto scroll-smooth"
          : "flex h-screen w-full flex-col items-center justify-start bg-background p-4 sm:p-6 pt-2 sm:pt-6 overflow-y-auto scroll-smooth"
      }
    >
      <div className={isEditFlow ? (embedded ? "w-full flex flex-col gap-5" : "w-full max-w-4xl flex flex-col gap-5") : "w-full max-w-2xl flex flex-col gap-4"}>
        {/* Header with App Logo */}
        {!embedded && (
        <div className={isEditFlow ? "flex items-start justify-between gap-4 px-2" : "flex flex-col items-center gap-3 text-center"}>
          {isEditFlow ? (
            <>
              <div className="flex items-start gap-4">
                <div className="bg-primary/10 p-3 rounded-2xl border border-primary/20 shadow-inner">
                  <ShellIcon className="h-6 w-6 text-primary" />
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground/50">
                    {shellCopy.kicker}
                  </div>
                  <h1 className="text-2xl font-bold tracking-tight">{shellCopy.title}</h1>
                  <p className="text-sm text-muted-foreground max-w-xl">{shellCopy.subtitle}</p>
                </div>
              </div>
              {onExit && (
                <Button variant="ghost" size="sm" className="gap-2 mt-1" onClick={onExit}>
                  <X className="h-4 w-4" />
                  Close
                </Button>
              )}
            </>
          ) : (
            <>
              {onExit && (
                <div className="w-full flex justify-end">
                  <Button variant="ghost" size="sm" className="gap-2" onClick={onExit}>
                    <X className="h-4 w-4" />
                    Close
                  </Button>
                </div>
              )}
              <div className="bg-primary/10 p-3 rounded-2xl border border-primary/20 shadow-inner group">
                <ShellIcon className="h-8 w-8 text-primary animate-pulse group-hover:rotate-12 transition-transform duration-500" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 justify-center">
                  <span className="text-4xl font-bold tracking-tight text-foreground">
                    Job <span className="text-primary">Radar</span>
                  </span>
                </div>
                <div className="flex flex-col items-center">
                  <h1 className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/30 text-center">
                    {shellCopy.kicker}
                  </h1>
                </div>
              </div>
            </>
          )}
        </div>
        )}

        {/* Stepper */}
        {currentStep > 0 && (
          isEditFlow ? (
            <div className={embedded ? "" : "px-2"}>
              <div className="rounded-2xl border border-border/40 bg-background/50 px-4 py-3 shadow-sm">
                <div className="flex items-center justify-between gap-4 text-[11px]">
                  <div className="font-semibold text-foreground">
                    Step {progressCurrent} of {progressTotal}
                  </div>
                  <div className="text-muted-foreground">
                    {stepperConfig.steps[stepperConfig.currentStep]}
                  </div>
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/40">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="px-4">
              <WizardStepper 
                steps={stepperConfig.steps}
                currentStep={stepperConfig.currentStep}
                completedSteps={stepperConfig.completedSteps}
              />
            </div>
          )
        )}

        {/* Step Content Container */}
        <div className={isEditFlow
          ? "relative mt-0 min-h-[300px] flex flex-col"
          : "relative mt-0 min-h-[300px] flex flex-col bg-muted/5 border border-border/30 rounded-3xl p-4 sm:p-6 backdrop-blur-sm shadow-sm"}>
          {/* Subtle background glow */}
          {!isEditFlow && (
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full bg-radial-gradient from-primary/5 to-transparent -z-10 pointer-events-none" />
          )}
          
          <div className="w-full">
            {renderStep()}
          </div>
        </div>

        {/* Footer Info */}
        {!isEditFlow && (
          <p className="text-center text-[10px] text-muted-foreground/40 uppercase tracking-widest font-mono">
            Job Radar v1.2 &bull; AI Powered Onboarding
          </p>
        )}
      </div>
    </div>
  )
}
