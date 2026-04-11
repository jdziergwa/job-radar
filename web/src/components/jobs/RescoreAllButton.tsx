'use client'

import { useState } from 'react'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { RefreshCw, Play, Loader2 } from 'lucide-react'
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

  const openProgressDialog = (nextRunId: string) => {
    setRunId(nextRunId)

    // Let the confirmation dialog fully close before showing progress.
    window.setTimeout(() => {
      setShowProgress(true)
    }, 0)
  }

  const handleRescoreAll = async () => {
    setConfirmOpen(false)
    setLoading(true)
    try {
      const { data, error } = await api.POST('/api/jobs/rescore/all', { 
        params: { query: { profile: 'default' } } 
      })
      
      if (error) {
        toast.error('Failed to start bulk rescore')
        console.error('Rescore all error:', error)
      } else {
        const id = data?.run_id
        if (!id) {
          toast.error('Bulk rescore did not return a run ID')
          return
        }

        toast.success('Bulk rescore started in background')
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
      onClick={() => setConfirmOpen(true)}
      disabled={loading}
      className={`gap-2 ${className}`}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <RefreshCw className="h-4 w-4" />
      )}
      {showText && (loading ? 'Rescoring...' : 'Rescore All')}
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
            Rescore all jobs in background
          </TooltipContent>
        </Tooltip>
      ) : (
        buttonContent
      )}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md border-border/50 bg-background/95 backdrop-blur-xl shadow-2xl">
          <DialogHeader>
            <DialogTitle>Rescore All Jobs?</DialogTitle>
            <DialogDescription className="pt-2">
              This will re-evaluate every job using the current profile and AI scoring. It may take several minutes to complete based on your database size.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0 mt-4">
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleRescoreAll} className="gap-2 bg-primary hover:bg-primary/90 shadow-lg">
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
          setShowProgress(false);
          window.dispatchEvent(new Event('pipeline-finished'));
        }}
      />
    </>
  )
}
