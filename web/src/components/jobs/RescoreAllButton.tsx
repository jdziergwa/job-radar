'use client'

import { useState } from 'react'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { AlertTriangle, CalendarClock, Loader2, Play, RefreshCw, RotateCcw, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PipelineProgressDialog } from '../pipeline/PipelineProgressDialog'

type RescoreScope = 'failed_recent' | 'unscored_new' | 'recent_scored' | 'all'

type ScopeOption = {
  scope: RescoreScope
  label: string
  description: string
  days: number
  icon: typeof AlertTriangle
  advanced?: boolean
}

const SCOPE_OPTIONS: ScopeOption[] = [
  {
    scope: 'failed_recent',
    label: 'Failed recent',
    description: 'Retry jobs from the last week that ended with scorer errors.',
    days: 7,
    icon: AlertTriangle,
  },
  {
    scope: 'unscored_new',
    label: 'Unscored new',
    description: 'Score saved jobs that have not received any score yet.',
    days: 7,
    icon: Sparkles,
  },
  {
    scope: 'recent_scored',
    label: 'Last 7 days',
    description: 'Refresh jobs scored during the last week.',
    days: 7,
    icon: CalendarClock,
  },
  {
    scope: 'all',
    label: 'All eligible jobs',
    description: 'Advanced: rescore the full saved history.',
    days: 365,
    icon: RotateCcw,
    advanced: true,
  },
]

interface RescoreAllButtonProps {
  variant?: 'default' | 'outline' | 'secondary' | 'ghost'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  className?: string
  showText?: boolean
}

export function RescoreAllButton({ 
  variant = 'outline', 
  size = 'sm', 
  className = '',
  showText = true
}: RescoreAllButtonProps) {
  const [loading, setLoading] = useState(false)
  const [showProgress, setShowProgress] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [runId, setRunId] = useState<string | null>(null)
  const [selectedScope, setSelectedScope] = useState<RescoreScope>('failed_recent')
  const [previewCounts, setPreviewCounts] = useState<Partial<Record<RescoreScope, number>>>({})
  const [previewLoading, setPreviewLoading] = useState(false)

  const openProgressDialog = (nextRunId: string) => {
    setRunId(nextRunId)

    // Let the confirmation dialog fully close before showing progress.
    window.setTimeout(() => {
      setShowProgress(true)
    }, 0)
  }

  const fetchPreviews = async () => {
    setPreviewLoading(true)
    try {
      const entries = await Promise.all(
        SCOPE_OPTIONS.map(async (option) => {
          const { data } = await api.GET('/api/jobs/rescore/preview', {
            params: {
              query: {
                profile: 'default',
                scope: option.scope,
                days: option.days,
              },
            },
          })
          return [option.scope, data?.count ?? 0] as const
        })
      )
      setPreviewCounts(Object.fromEntries(entries))
    } catch (err) {
      toast.error('Could not load rescore counts')
      console.error(err)
    } finally {
      setPreviewLoading(false)
    }
  }

  const openConfirm = () => {
    setConfirmOpen(true)
    void fetchPreviews()
  }

  const handleRescore = async () => {
    setConfirmOpen(false)
    setLoading(true)
    const option = SCOPE_OPTIONS.find((item) => item.scope === selectedScope) ?? SCOPE_OPTIONS[0]
    try {
      const { data, error } = await api.POST('/api/jobs/rescore', { 
        params: { query: { profile: 'default' } },
        body: {
          scope: option.scope,
          days: option.days,
        },
      })
      
      if (error) {
        toast.error('Failed to start rescore')
        console.error('Rescore error:', error)
      } else {
        const id = data?.run_id
        if (!id) {
          toast.error('Rescore did not return a run ID')
          return
        }

        toast.success(`${option.label} rescore started`)
        openProgressDialog(id)
        window.dispatchEvent(new CustomEvent('pipeline-started', { 
          detail: { run_id: id } 
        }))
      }
    } catch (err) {
      toast.error('An unexpected error occurred')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const buttonContent = (
    <Button
      variant={variant}
      size={size}
      onClick={openConfirm}
      disabled={loading}
      className={`gap-2 ${className}`}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <RefreshCw className="h-4 w-4" />
      )}
      {showText && (loading ? 'Rescoring...' : 'Rescore')}
    </Button>
  )

  return (
    <>
      {!showText ? (
        <Tooltip>
          <TooltipTrigger>
            {buttonContent}
          </TooltipTrigger>
          <TooltipContent align="center" side="top">
            Choose jobs to rescore
          </TooltipContent>
        </Tooltip>
      ) : (
        buttonContent
      )}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md border-border/50 bg-background/95 backdrop-blur-xl shadow-2xl">
          <DialogHeader>
            <DialogTitle>Choose Rescore Scope</DialogTitle>
            <DialogDescription className="pt-2">
              Re-evaluate a focused group of jobs using the current profile and AI scoring.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-2">
            {SCOPE_OPTIONS.map((option) => {
              const Icon = option.icon
              const selected = selectedScope === option.scope
              const count = previewCounts[option.scope]

              return (
                <button
                  key={option.scope}
                  type="button"
                  onClick={() => setSelectedScope(option.scope)}
                  className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
                    selected
                      ? 'border-primary bg-primary/10 text-foreground'
                      : 'border-border/50 bg-background hover:bg-muted/50'
                  }`}
                >
                  <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${option.advanced ? 'text-amber-500' : 'text-primary'}`} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold">{option.label}</span>
                      <span className="shrink-0 text-xs font-semibold text-muted-foreground">
                        {previewLoading ? '...' : `${count ?? 0} jobs`}
                      </span>
                    </span>
                    <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
                      {option.description}
                    </span>
                  </span>
                </button>
              )
            })}
          </div>

          <DialogFooter className="gap-2 sm:gap-0 mt-4">
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleRescore}
              disabled={loading || previewLoading || (previewCounts[selectedScope] ?? 0) === 0}
              className="gap-2 bg-primary hover:bg-primary/90 shadow-lg"
            >
              <Play className="h-4 w-4 fill-current" /> Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PipelineProgressDialog
        runId={runId}
        open={showProgress}
        onOpenChange={setShowProgress}
        mode="rescore"
        onComplete={() => {
          window.dispatchEvent(new Event('pipeline-finished'));
        }}
      />
    </>
  )
}
