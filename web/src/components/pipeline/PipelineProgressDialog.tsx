'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/lib/api/client'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Loader2, CheckCircle2, AlertCircle, Terminal, FastForward, Clock, XCircle, History, Zap } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const STEPS = [
  'Starting',
  'Collecting',
  'Deduplicating',
  'Pre-filtering',
  'Scoring',
  'Done'
]

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return ''
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const remSeconds = Math.floor(seconds % 60)
  return `${minutes}m ${remSeconds}s`
}

interface PipelineProgressDialogProps {
  runId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onComplete?: () => void
}

export function PipelineProgressDialog({ runId, open, onOpenChange, onComplete }: PipelineProgressDialogProps) {
  const [status, setStatus] = useState<any>(null)
  const [isCancelling, setIsCancelling] = useState(false)
  const pollInterval = useRef<NodeJS.Timeout | null>(null)

  const fetchStatus = useCallback(async (id: string) => {
    try {
      const { data } = await api.GET('/api/pipeline/status/{run_id}', {
        params: { path: { run_id: id } }
      })
      if (data) {
        setStatus(data)
        if (data.status !== 'running') {
          if (pollInterval.current) clearInterval(pollInterval.current)
          pollInterval.current = null
          
          if (data.status === 'done' && onComplete) {
            onComplete()
          }
        }
      }
    } catch (err) {
      console.error('Status fetch failed:', err)
    }
  }, [onComplete])

  useEffect(() => {
    if (open && runId) {
      fetchStatus(runId)
      pollInterval.current = setInterval(() => fetchStatus(runId), 2000)
    } else {
      if (pollInterval.current) clearInterval(pollInterval.current)
      pollInterval.current = null
    }
    return () => { if (pollInterval.current) clearInterval(pollInterval.current) }
  }, [open, runId, fetchStatus])

  const handleCancel = async () => {
    if (!runId) return
    setIsCancelling(true)
    try {
      await api.POST('/api/pipeline/cancel/{run_id}', {
        params: { path: { run_id: runId } }
      })
    } catch (err) {
      console.error('Failed to cancel pipeline:', err)
    } finally {
      setIsCancelling(false)
    }
  }

  const currentStep = status?.step || 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl border-border/50 bg-background/85 backdrop-blur-xl shadow-2xl overflow-hidden">
        <DialogHeader className="pb-4 border-b border-border/50">
          <div className="flex items-center gap-3">
             <div className="bg-primary/20 p-2 rounded-xl text-primary">
                <Loader2 className={`h-5 w-5 ${status?.status === 'running' ? 'animate-spin' : ''}`} />
             </div>
             <div>
                <DialogTitle className="text-xl">
                  {status?.status === 'done' ? 'Pipeline Complete' : 'Executing Intelligence Tasks'}
                </DialogTitle>
                <DialogDescription>AI Agents are processing your request.</DialogDescription>
             </div>
          </div>
        </DialogHeader>

        <div className="py-8 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
             {/* Stepper */}
             <div className="relative flex justify-between px-2">
                <div className="absolute top-4 left-0 w-full h-0.5 bg-muted/30 -z-10" />
                <div 
                  className="absolute top-4 left-0 h-0.5 bg-primary transition-all duration-700 ease-in-out -z-10" 
                  style={{ width: `${(currentStep / (STEPS.length - 1)) * 100}%` }}
                />
                {STEPS.map((step, idx) => {
                   const isSkipped = status?.skipped_steps?.includes(idx)
                   const isCompleted = idx < currentStep && !isSkipped
                   const isActive = idx === currentStep && !isSkipped

                   return (
                      <div key={step} className="flex flex-col items-center gap-2 group">
                         <div className={`h-8 w-8 rounded-full border-2 flex items-center justify-center transition-all duration-500 cursor-default ${
                           isSkipped ? 'bg-amber-500/10 border-amber-500/50 text-amber-500 shadow-sm' :
                           isCompleted ? 'bg-primary border-primary text-white scale-110 shadow-lg' :
                           isActive ? 'bg-background border-primary text-primary shadow-sm scale-110 animate-pulse' :
                           'bg-background border-muted text-muted-foreground opacity-50'
                         }`}>
                            {isSkipped ? <FastForward className="h-4 w-4" /> : 
                             isCompleted ? <CheckCircle2 className="h-4 w-4" /> : 
                             <span className="text-[10px] font-bold">{idx + 1}</span>}
                         </div>
                         <span className={`text-[9px] font-bold uppercase tracking-tight transition-all ${
                           isSkipped ? 'text-amber-500/70' :
                           idx <= currentStep ? 'text-foreground' : 
                           'text-muted-foreground opacity-50'
                         }`}>{step}</span>
                      </div>
                   )
                })}
             </div>

             {/* Terminal View */}
             <div className="bg-black/90 rounded-2xl p-6 font-mono text-sm shadow-2xl border border-white/10 group">
                <div className="flex items-center gap-2 mb-4 border-b border-white/10 pb-3">
                   <div className="flex gap-1.5 ml-auto">
                      {status?.status === 'running' && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={handleCancel}
                          disabled={isCancelling}
                          className="h-6 px-2 text-[9px] font-bold uppercase tracking-widest text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors gap-1.5 border border-red-500/20"
                        >
                          {isCancelling ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <XCircle className="h-2.5 w-2.5" />}
                          Stop
                        </Button>
                      )}
                      <div className="h-2 w-2 rounded-full bg-red-500/30" />
                      <div className="h-2 w-2 rounded-full bg-amber-500/30" />
                      <div className="h-2 w-2 rounded-full bg-emerald-500/30" />
                   </div>
                </div>
                <div className="space-y-3 min-h-[160px] max-h-[300px] overflow-auto">
                   {status?.step_name && (
                      <div className="flex items-center justify-between group/row pr-2">
                        <p className="text-white/90 flex gap-3">
                           <span className="text-primary font-bold">»</span>
                           Currently: <span className="font-bold underline underline-offset-4 decoration-primary/30">{status.step_name}</span>
                        </p>
                        {status.duration !== undefined && status.duration > 0 && (
                          <div className="flex items-center gap-1.5 text-[10px] text-primary/60 font-mono bg-primary/5 px-2 py-0.5 rounded-md border border-primary/10">
                            <Clock className="h-3 w-3" />
                            {formatDuration(status.duration)}
                          </div>
                        )}
                      </div>
                   )}
                   {status?.detail && (
                      <p className="text-white/60 flex gap-3 pl-6">
                         <span className="opacity-40">→</span>
                         <span className="italic">{status.detail}</span>
                      </p>
                   )}
                   {status?.stats && Object.entries(status.stats).map(([k, v]) => (
                      <p key={k} className="text-white/60 flex gap-3 pl-6">
                         <span className="opacity-40">-</span>
                         <span className="capitalize">{k.replace(/_/g, ' ')}:</span>
                         <span className="text-white font-bold">{String(v)}</span>
                      </p>
                   ))}
                   {status?.error && (
                      <div className="bg-red-500/10 border border-red-500/20 p-3 rounded-lg flex gap-3 mt-4">
                         <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                         <span className="text-red-400 text-xs leading-relaxed">{status.error}</span>
                      </div>
                   )}
                   {status?.status === 'done' && (
                      <div className="pt-4 text-emerald-500 font-bold flex flex-col gap-2">
                         <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-4 w-4" />
                            Completed successfully.
                         </div>
                         <Button onClick={() => onOpenChange(false)} variant="outline" size="sm" className="w-fit text-xs">Close</Button>
                      </div>
                   )}
                </div>
             </div>
          </div>

        <DialogFooter className={`pt-4 border-t border-border/50 text-[10px] text-muted-foreground flex items-center sm:justify-between`}>
          <div className="flex items-center gap-2">
             <History className="h-3 w-3" />
             Pipeline Active
          </div>
          <Badge variant="outline" className="font-mono text-[9px] border-border/30 px-1 opacity-50">v1.2.0-stable</Badge>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
