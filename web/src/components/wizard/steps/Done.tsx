'use client'

import { Button } from '@/components/ui/button'
import { CheckCircle2, Settings, ArrowRight, Sparkles } from 'lucide-react'
import Link from 'next/link'

import { StepProps } from '../types'

export function Done({ onNext, onBack, onUpdate, data }: StepProps) {
  const isEditFlow = data.wizardFlowMode === 'edit_preferences' || data.wizardFlowMode === 'update_cv'

  return (
    <div className="flex flex-col items-center gap-6 py-6 animate-in fade-in slide-in-from-bottom-8 duration-700 max-w-md mx-auto text-center">
      <div className="relative">
        {/* Decorative sparkles */}
        <div className="absolute -top-4 -left-4 animate-bounce delay-100">
          <Sparkles className="h-5 w-5 text-amber-400" />
        </div>
        <div className="absolute -bottom-2 -right-6 animate-pulse delay-500">
          <Sparkles className="h-4 w-4 text-emerald-400" />
        </div>
        
        <div className="bg-emerald-500/10 p-4 rounded-full border border-emerald-500/20 shadow-2xl shadow-emerald-500/10">
          <CheckCircle2 className="h-12 w-12 text-emerald-500 animate-in zoom-in-50 duration-500" />
        </div>
      </div>

      <div className="space-y-1">
        <h2 className="text-2xl font-bold tracking-tight">
          {isEditFlow ? 'Your Updates Are Ready!' : 'Your Profile is Ready!'}
        </h2>
        <div className="space-y-4">
          <p className="text-muted-foreground leading-relaxed">
            {isEditFlow
              ? 'Your saved profile has been regenerated from the updated guided settings.'
              : 'Job Radar is now configured to find jobs matching your exact experience and preferences.'}
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            <div className="px-3 py-1 bg-primary/5 rounded-full border border-primary/10 text-[10px] font-bold uppercase tracking-widest text-primary/70">
              AI Rules Generated
            </div>
            <div className="px-3 py-1 bg-primary/5 rounded-full border border-primary/10 text-[10px] font-bold uppercase tracking-widest text-primary/70">
              Scoring Philosophy Applied
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col w-full gap-3 pt-4">
        <Button 
          onClick={() => onNext()} 
          className="h-14 text-lg font-bold shadow-xl shadow-primary/20 gap-2 rounded-2xl bg-primary hover:bg-primary/90 hover:scale-[1.02] transition-all"
        >
          {isEditFlow ? 'Back to settings' : 'Start searching for jobs'}
          <ArrowRight className="h-5 w-5" />
        </Button>
        <Link href="/settings" className="w-full">
          <Button 
            variant="outline" 
            className="w-full h-12 text-sm rounded-xl border-border/50 hover:bg-muted/30 gap-2 text-muted-foreground hover:text-foreground transition-all"
          >
            <Settings className="h-4 w-4" />
            Fine-tune in Settings
          </Button>
        </Link>
      </div>

      <p className="text-[11px] text-muted-foreground/50 italic px-8">
        {isEditFlow
          ? 'You can reopen this guided editor any time from Settings.'
          : 'You can always update your profile, matching rules, or AI parameters in the Settings tab.'}
      </p>
    </div>
  )
}
