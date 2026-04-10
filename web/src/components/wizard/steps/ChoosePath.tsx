'use client'

import { useState } from 'react'
import { Sparkles, PenLine, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'

import { StepProps } from '../types'

export function ChoosePath({ onNext, onBack, onUpdate, data }: StepProps) {
  return (
    <div className="flex flex-col gap-6 py-2 animate-in fade-in slide-in-from-bottom-4 duration-500 w-full">
      <div className="text-center space-y-1 bg-background/50 py-4 -mt-4 border-b border-border/10 mb-2 w-full">
        <h2 className="text-xl font-bold tracking-tight">How would you like to start?</h2>
        <p className="text-muted-foreground text-xs max-w-sm mx-auto">Select your onboarding preference to continue.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full px-2">
        {/* AI Path */}
        <button
          onClick={() => onNext({ path: 'ai' })}
          className={cn(
            "flex flex-col text-left p-6 rounded-3xl border-2 transition-all cursor-pointer group relative overflow-hidden bg-white dark:bg-card/50 backdrop-blur-sm",
            "border-border/50 hover:border-primary hover:bg-primary/5 hover:shadow-xl hover:shadow-primary/5 hover:-translate-y-1 active:scale-[0.98]"
          )}
        >
          <div className="flex items-start justify-between mb-4">
            <div className="p-4 rounded-2xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-white transition-all duration-300">
              <Sparkles className="h-7 w-7" />
            </div>
            <div className="h-6 w-6 rounded-full border border-border/50 flex items-center justify-center opacity-0 group-hover:opacity-100 group-hover:scale-110 transition-all">
                <CheckCircle2 className="h-4 w-4 text-primary" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
                <h3 className="font-bold text-xs uppercase tracking-widest text-primary">AI Powered</h3>
            </div>
            <h4 className="text-xl font-bold">Upload CV</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Upload your CV as PDF. AI extracts your profile in ~30 seconds.
            </p>
          </div>
          <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-between gap-3 text-[11px]">
            <span className="font-medium text-muted-foreground/70">Claude Sonnet</span>
            <span className="font-medium text-primary/70 text-right">~2 AI calls, est. $0.15</span>
          </div>
        </button>

        {/* Manual Path */}
        <button
          onClick={() => onNext({ path: 'manual' })}
          className={cn(
            "flex flex-col text-left p-6 rounded-3xl border-2 transition-all cursor-pointer group relative overflow-hidden bg-white dark:bg-card/50 backdrop-blur-sm",
            "border-border/50 hover:border-primary hover:bg-primary/5 hover:shadow-xl hover:shadow-primary/5 hover:-translate-y-1 active:scale-[0.98]"
          )}
        >
          <div className="flex items-start justify-between mb-4">
            <div className="p-4 rounded-2xl bg-muted text-muted-foreground group-hover:bg-primary group-hover:text-white transition-all duration-300">
              <PenLine className="h-7 w-7" />
            </div>
            <div className="h-6 w-6 rounded-full border border-border/50 flex items-center justify-center opacity-0 group-hover:opacity-100 group-hover:scale-110 transition-all">
                <CheckCircle2 className="h-4 w-4 text-primary" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
                <h3 className="font-bold text-xs uppercase tracking-widest opacity-50">Local Only</h3>
            </div>
            <h4 className="text-xl font-bold">Set up manually</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Start from a template, review the files, and save your profile.
            </p>
          </div>
          <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-between gap-3 text-[11px]">
            <span className="font-medium text-muted-foreground/70">No API calls</span>
            <span className="font-medium text-muted-foreground/70">Free</span>
          </div>
        </button>
      </div>
    </div>
  )
}
