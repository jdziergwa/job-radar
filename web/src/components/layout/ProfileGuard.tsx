'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Loader2, Radar, ArrowRight, CheckCircle2 } from 'lucide-react'
import { QuickStartWizard } from '@/components/wizard/QuickStartWizard'

type Step = 'checking' | 'setup' | 'saving' | 'done' | 'ready'

export function ProfileGuard({ children }: { children: React.ReactNode }) {
  const [step, setStep] = useState<Step>('checking')
  const [docContent, setDocContent] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function checkProfile() {
      try {
        const res = await api.GET('/api/profile/{name}/yaml', {
          params: { path: { name: 'default' } },
        })
        setStep(res.error ? 'setup' : 'ready')
      } catch {
        setStep('setup')
      }
    }
    checkProfile()
  }, [])

  const handleCreate = async () => {
    setError(null)
    setStep('saving')
    try {
      // Create profile directory from example template
      const createRes = await fetch('/api/profile/default', { method: 'POST' })
      if (!createRes.ok && createRes.status !== 409) {
        throw new Error('Failed to create profile')
      }

      // Write the CV if the user provided one
      if (docContent.trim()) {
        const docRes = await api.PUT('/api/profile/{name}/doc', {
          params: { path: { name: 'default' } },
          body: { content: docContent },
        })
        if (docRes.error) throw new Error('Failed to save resume')
      }

      setStep('done')
      setTimeout(() => setStep('ready'), 1200)
    } catch (err: any) {
      setError(err.message || 'Something went wrong')
      setStep('setup')
    }
  }

  if (step === 'checking') {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (step === 'ready' || step === 'done') {
    if (step === 'done') {
      return (
        <div className="flex h-screen w-screen items-center justify-center bg-background p-6">
          <div className="flex flex-col items-center gap-4 text-center animate-in fade-in zoom-in duration-500">
            <div className="bg-emerald-500/20 p-4 rounded-full">
              <CheckCircle2 className="h-12 w-12 text-emerald-500" />
            </div>
            <div className="space-y-2">
              <p className="font-bold text-2xl tracking-tight">Profile synchronised!</p>
              <p className="text-muted-foreground">Loading your personalized dashboard…</p>
            </div>
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/40 animate-pulse" />
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/40 animate-pulse delay-75" />
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/40 animate-pulse delay-150" />
            </div>
          </div>
        </div>
      )
    }
    return <>{children}</>
  }

  // setup or saving
  if (step === 'setup') {
    return (
      <QuickStartWizard 
        onComplete={() => {
          setStep('done')
          setTimeout(() => setStep('ready'), 1500)
        }} 
      />
    )
  }

  // saving state (used for manual creation or transitions)
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest">
          Finalizing configuration…
        </p>
      </div>
    </div>
  )
}
