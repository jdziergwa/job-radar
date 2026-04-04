'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Loader2, Radar, ArrowRight, CheckCircle2 } from 'lucide-react'

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
        <div className="flex h-screen w-screen items-center justify-center bg-background">
          <div className="flex flex-col items-center gap-3 text-center">
            <CheckCircle2 className="h-10 w-10 text-emerald-500" />
            <p className="font-medium text-lg">Profile created!</p>
            <p className="text-sm text-muted-foreground">Loading your dashboard…</p>
          </div>
        </div>
      )
    }
    return <>{children}</>
  }

  // setup or saving
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-xl flex flex-col gap-6">
        {/* Header */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="bg-primary/10 p-4 rounded-2xl">
            <Radar className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Welcome to Job Radar</h1>
          <p className="text-muted-foreground text-sm max-w-sm">
            Paste your CV or experience summary below. The AI uses it to score how well each job matches you.
            You can always edit this later in Settings.
          </p>
        </div>

        {/* CV textarea */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-mono uppercase tracking-widest text-muted-foreground/70">
            Your CV / Experience Summary
          </label>
          <textarea
            className="w-full h-56 rounded-xl border border-border/60 bg-muted/20 p-4 font-mono text-sm leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder:text-muted-foreground/40"
            placeholder={`## Role Target\nSenior Backend Engineer — remote, European timezones\n\n## Experience\n- 8 years Python / Go / TypeScript\n- Current: Staff Eng at Acme Corp (remote)\n...\n\n(Leave blank to start with placeholder text and fill in later)`}
            value={docContent}
            onChange={(e) => setDocContent(e.target.value)}
            spellCheck={false}
            disabled={step === 'saving'}
          />
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-4 py-2">
            {error}
          </p>
        )}

        <Button
          onClick={handleCreate}
          disabled={step === 'saving'}
          className="w-full gap-2 h-11 text-base"
        >
          {step === 'saving' ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Setting up…</>
          ) : (
            <>Get Started <ArrowRight className="h-4 w-4" /></>
          )}
        </Button>

        <p className="text-center text-xs text-muted-foreground/50">
          Matching rules (keywords, locations, scoring model) start from sensible defaults.
          Tune them any time in <span className="text-muted-foreground">Settings → Matching Rules</span>.
        </p>
      </div>
    </div>
  )
}
