'use client'

import { CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface WizardStepperProps {
  steps: string[]
  currentStep: number
  completedSteps: number[]
}

export function WizardStepper({ steps, currentStep, completedSteps }: WizardStepperProps) {
  return (
    <div className="relative flex justify-between w-full px-2 py-4">
      {/* Background Track */}
      <div className="absolute top-8 left-6 right-6 h-0.5 bg-muted/50 -z-10" />
      
      {/* Active Progress line */}
      <div 
        className="absolute top-8 left-6 h-0.5 bg-primary transition-all duration-700 ease-in-out -z-10" 
        style={{ width: `calc(${(currentStep / (steps.length - 1)) * 100}% - 48px)` }}
      />
      
      {steps.map((step, idx) => {
        const isCompleted = completedSteps.includes(idx) || idx < currentStep || (idx === currentStep && idx === steps.length - 1)
        const isActive = idx === currentStep

        return (
          <div key={idx} className="flex flex-col items-center gap-2 group">
            <div className={`h-8 w-8 rounded-full border-2 flex items-center justify-center transition-all duration-500 cursor-default relative z-10 ${
              isCompleted ? 'bg-primary border-primary text-white scale-110 shadow-lg' :
              isActive ? 'bg-background border-primary text-primary shadow-sm scale-110 animate-pulse' :
              'bg-background border-muted text-muted-foreground opacity-50'
            }`}>
              {isCompleted ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <span className="text-[10px] font-bold">{idx + 1}</span>
              )}
            </div>
            
            <span className={`text-[9px] font-bold uppercase tracking-tight transition-all text-center whitespace-nowrap ${
              idx <= currentStep ? 'text-foreground' : 
              'text-muted-foreground opacity-50'
            }`}>
              {step}
            </span>
          </div>
        )
      })}
    </div>
  )
}
