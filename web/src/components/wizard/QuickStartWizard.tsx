'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { WizardStepper } from './WizardStepper'
import { ChoosePath } from './steps/ChoosePath'
import { UploadCV } from './steps/UploadCV'
import { AIAnalysis } from './steps/AIAnalysis'
import { ReviewProfile } from './steps/ReviewProfile'
import { SearchLocation } from './steps/SearchLocation'
import { PreferencesGoals } from './steps/PreferencesGoals'
import { ReviewGenerate } from './steps/ReviewGenerate'
import { Done } from './steps/Done'
import { Radar } from 'lucide-react'
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
}

export function QuickStartWizard({ onComplete }: QuickStartWizardProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [wizardData, setWizardData] = useState<Partial<WizardData>>({})
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [isInitialized, setIsInitialized] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Reset scroll on step change
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({ top: 0, behavior: 'instant' })
    }
  }, [currentStep])

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('job-radar-wizard-state')
    if (saved) {
      try {
        const { currentStep: savedStep, wizardData: savedData, completedSteps: savedCompleted } = JSON.parse(saved)
        setCurrentStep(savedStep || 0)
        setWizardData(savedData || {})
        setCompletedSteps(savedCompleted || [])
      } catch (err) {
        console.error("Failed to restore wizard state", err)
      }
    }
    setIsInitialized(true)
  }, [])

  // Save to localStorage on changes
  useEffect(() => {
    if (!isInitialized) return
    localStorage.setItem('job-radar-wizard-state', JSON.stringify({
      currentStep,
      wizardData,
      completedSteps
    }))
  }, [currentStep, wizardData, completedSteps, isInitialized])

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
      localStorage.removeItem('job-radar-wizard-state')
      onComplete()
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }, [currentStep, onComplete, wizardData])

  const handleBack = useCallback((backData?: Partial<WizardData>) => {
    if (backData) {
      setWizardData((prev) => ({ ...prev, ...backData }))
    }
    if (currentStep > 0) {
      if (wizardData?.path === 'manual' && currentStep === 6) {
        setCurrentStep(0)
      } else {
        setCurrentStep((prev) => prev - 1)
      }
    }
  }, [currentStep, wizardData?.path])

  const renderStep = () => {
    const props = {
      onNext: handleNext,
      onBack: handleBack,
      data: wizardData
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

  return (
    <div 
      ref={scrollContainerRef}
      className="flex h-screen w-full flex-col items-center justify-start bg-background p-4 sm:p-6 pt-2 sm:pt-6 overflow-y-auto scroll-smooth"
    >
      <div className="w-full max-w-2xl flex flex-col gap-4">
        {/* Header with App Logo */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="bg-primary/10 p-3 rounded-2xl border border-primary/20 shadow-inner group">
            <Radar className="h-8 w-8 text-primary animate-pulse group-hover:rotate-12 transition-transform duration-500" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2 justify-center">
              <span className="text-4xl font-bold tracking-tight text-foreground">
                Job <span className="text-primary">Radar</span>
              </span>
            </div>
            <div className="flex flex-col items-center">
              <h1 className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/30 text-center">
                Onboarding Wizard
              </h1>
            </div>
          </div>
        </div>

        {/* Stepper */}
        {currentStep > 0 && (
          <div className="px-4">
            <WizardStepper 
              steps={wizardData?.path === 'manual' ? [STEPS[0], STEPS[6], STEPS[7]] : STEPS} 
              currentStep={
                wizardData?.path === 'manual' 
                  ? (currentStep === 0 ? 0 : currentStep === 6 ? 1 : 2)
                  : currentStep
              } 
              completedSteps={
                wizardData?.path === 'manual'
                  ? completedSteps.map(idx => (idx === 0 ? 0 : idx === 6 ? 1 : idx === 7 ? 2 : -1)).filter(idx => idx !== -1)
                  : completedSteps
              } 
            />
          </div>
        )}

        {/* Step Content Container */}
        <div className="relative mt-0 min-h-[300px] flex flex-col bg-muted/5 border border-border/30 rounded-3xl p-4 sm:p-6 backdrop-blur-sm shadow-sm">
          {/* Subtle background glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full bg-radial-gradient from-primary/5 to-transparent -z-10 pointer-events-none" />
          
          <div className="w-full">
            {renderStep()}
          </div>
        </div>

        {/* Footer Info */}
        <p className="text-center text-[10px] text-muted-foreground/40 uppercase tracking-widest font-mono">
          Job Radar v1.2 &bull; AI Powered Onboarding
        </p>
      </div>
    </div>
  )
}
