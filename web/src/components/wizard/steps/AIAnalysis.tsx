'use client'

import { Loader2, Sparkles, BrainCircuit, BarChart3, Fingerprint, AlertCircle, RefreshCw, PencilLine } from 'lucide-react'
import { useEffect, useState, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface StepProps {
  onNext: (data?: any) => void
  onBack: (data?: any) => void
  data: any
}

const MESSAGES = [
  { icon: Sparkles, text: "Reading your experience..." },
  { icon: BrainCircuit, text: "Identifying skills and expertise..." },
  { icon: BarChart3, text: "Mapping your career trajectory..." },
  { icon: Fingerprint, text: "Generating suggestions..." },
]

export function AIAnalysis({ onNext, onBack, data }: StepProps) {
  const [msgIndex, setMsgIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const processedRef = useRef(false)

  useEffect(() => {
    const interval = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % MESSAGES.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (data.analysisPromise && !processedRef.current) {
      processedRef.current = true
      data.analysisPromise.then((res: any) => {
        if (res.data) {
          // Success! Auto-advance to ReviewProfile (Step 3)
          onNext({ cvAnalysis: res.data })
        } else {
          // Error case: extract error message
          const errorMsg = res.error?.detail || "CV Analysis failed. This can happen with very complex PDFs or temporary AI outages."
          setError(errorMsg)
        }
      }).catch((err: any) => {
        setError("Connection error. Please check your network or try again.")
      })
    }
  }, [data.analysisPromise, onNext])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-8 py-12 animate-in fade-in zoom-in-95 duration-500 text-center">
        <div className="bg-destructive/10 p-6 rounded-[2.5rem] border border-destructive/20 shadow-2xl shadow-destructive/5">
          <AlertCircle className="h-12 w-12 text-destructive animate-pulse" />
        </div>
        
        <div className="space-y-3 max-w-sm">
          <h2 className="text-2xl font-bold tracking-tight">Analysis Interrupted</h2>
          <p className="text-muted-foreground text-sm leading-relaxed px-4">
            {error}
          </p>
        </div>

        <div className="flex flex-col w-full max-w-xs gap-3">
          <Button 
            onClick={() => onBack({ retry: true })} 
            className="h-12 text-base font-bold shadow-lg gap-2 rounded-2xl"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </Button>
          <Button 
            onClick={() => onNext({ path: 'manual' })} 
            variant="ghost" 
            className="h-12 text-muted-foreground hover:bg-muted/50 rounded-2xl gap-2"
          >
            <PencilLine className="h-4 w-4" />
            Set up manually
          </Button>
        </div>
      </div>
    )
  }

  const StepIcon = MESSAGES[msgIndex].icon

  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-10 py-12 animate-in fade-in duration-700">
      <div className="relative">
        {/* Animated background glow */}
        <div className="absolute inset-0 bg-primary/20 blur-[100px] rounded-full scale-150 animate-pulse" />
        
        {/* Spinner container */}
        <div className="relative bg-background/40 backdrop-blur-xl border border-primary/20 rounded-[2.5rem] p-12 shadow-2xl flex items-center justify-center overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-tr from-primary/10 via-transparent to-primary/5 opacity-50" />
          <Loader2 className="h-16 w-16 animate-spin text-primary relative z-10" />
          
          {/* Decorative rotating border */}
          <div className="absolute inset-0 border-2 border-primary/10 rounded-[2.5rem] animate-[spin_10s_linear_infinite]" />
        </div>
      </div>
      
      <div className="text-center space-y-6 max-w-sm relative z-10">
        <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary font-bold uppercase tracking-widest text-[10px] shadow-sm">
          <StepIcon className="h-3.5 w-3.5 animate-bounce" />
          <span className="animate-in slide-in-from-bottom-2 duration-500 min-w-[220px]" key={msgIndex}>
            {MESSAGES[msgIndex].text}
          </span>
        </div>
        
        <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight">AI Analysis</h2>
            <p className="text-muted-foreground text-xs leading-relaxed px-4 max-w-xs mx-auto">
              Our models are extracting patterns from your CV. This usually takes 15-30 seconds.
            </p>
        </div>
      </div>

      {/* Progress indicators */}
      <div className="flex gap-3">
        {MESSAGES.map((_, i) => (
          <div 
            key={i} 
            className={cn(
              "h-1.5 rounded-full transition-all duration-1000",
              i === msgIndex ? "bg-primary w-8" : "bg-primary/20 w-1.5"
            )}
          />
        ))}
      </div>
    </div>
  )
}

