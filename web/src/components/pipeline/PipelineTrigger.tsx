'use client'

import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api/client'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Button, buttonVariants } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { Loader2, Play, Terminal, Zap, History, Info } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { PipelineProgressDialog } from './PipelineProgressDialog'
import type { components } from '@/lib/api/types'

type ProviderInfo = components['schemas']['ProviderInfo']

export function PipelineTrigger({ collapsed = false }: { collapsed?: boolean }) {
  const [open, setOpen] = useState(false)
  const [showProgress, setShowProgress] = useState(false)
  const [activeRun, setActiveRun] = useState<{ running: boolean; run_id: string | null } | null>(null)
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [dryRun, setDryRun] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [aggregatorStatus, setAggregatorStatus] = useState<{
    live_updated_at: string;
    local_updated_at: string;
    is_up_to_date: boolean;
    total_jobs: number;
  } | null>(null)

  const fetchActive = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/pipeline/active', {
        params: { query: { profile: 'default' } }
      })
      if (data) setActiveRun(data as any)
    } catch (err) {
      console.error('Failed to fetch active pipeline:', err)
    }
  }, [])

  const fetchAggregatorStatus = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/pipeline/aggregator/status', {
        params: { query: { profile: 'default' } }
      })
      if (data) setAggregatorStatus(data as any)
    } catch (err) {
      console.error('Failed to fetch aggregator status:', err)
    }
  }, [])

  const fetchProviders = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/pipeline/providers')
      if (data) {
        const p_list = data as ProviderInfo[];
        setProviders(p_list)
        // Default to all selected
        setSelectedSources(p_list.map(p => p.name))
      }
    } catch (err) {
      console.error('Failed to fetch providers:', err)
    }
  }, [])

  useEffect(() => {
    if (open) {
      fetchActive()
      fetchAggregatorStatus()
      fetchProviders()
    }
  }, [open, fetchActive, fetchAggregatorStatus, fetchProviders])

  const toggleSource = (name: string) => {
    setSelectedSources(prev => 
      prev.includes(name) 
        ? prev.filter(s => s !== name) 
        : [...prev, name]
    )
  }

  const selectAll = () => setSelectedSources(providers.map(p => p.name))
  const selectNone = () => setSelectedSources([])

  const handleStart = async () => {
    if (selectedSources.length === 0) {
      toast.error("Please select at least one source")
      return
    }
    setIsStarting(true)
    try {
      const { data, error } = await api.POST('/api/pipeline/run', {
        body: {
          profile: 'default',
          sources: selectedSources,
          dry_run: dryRun
        }
      })

      if (error) throw new Error(typeof error === 'string' ? error : 'Failed to start pipeline')
      if (data) {
        const runId = data.run_id
        setActiveRun({ running: true, run_id: runId })
        setShowProgress(true)
        setOpen(false)
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to start pipeline')
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger
          className={cn(
            buttonVariants({ variant: collapsed ? "ghost" : "default" }),
            "w-full group relative overflow-hidden transition-all duration-300",
            collapsed ? "px-0 justify-center" : "justify-start gap-3 bg-primary/95 hover:bg-primary shadow-lg"
          )}
        >
          {activeRun?.running ? (
            <Loader2 className="h-4 w-4 animate-spin text-white" />
          ) : (
            <Zap className={`h-4 w-4 transition-transform group-hover:scale-110 ${collapsed ? 'text-primary' : 'text-white'}`} />
          )}
          {!collapsed && (
            <div className="flex flex-col items-start leading-none text-left">
              <span className="text-xs font-bold uppercase tracking-wider">Run Pipeline</span>
              {activeRun?.running && <span className="text-[10px] opacity-70 animate-pulse mt-0.5">Active...</span>}
            </div>
          )}
        </DialogTrigger>
        <DialogContent className="relative flex max-h-[calc(100vh-2rem)] w-full flex-col gap-0 overflow-hidden border-border/50 bg-transparent p-0 shadow-2xl sm:max-w-3xl">
          <div className="pointer-events-none absolute inset-0 rounded-[inherit] bg-background/85 backdrop-blur-xl" />
          <DialogHeader className="relative z-10 shrink-0 border-b border-border/50 px-4 pb-4 pt-6 sm:px-6">
            <div className="flex items-center gap-3">
               <div className="bg-primary/20 p-2 rounded-xl text-primary">
                  <Zap className="h-5 w-5" />
               </div>
               <div>
                  <DialogTitle className="text-xl">Job Intelligence Pipeline</DialogTitle>
                  <DialogDescription>Trigger background collectors and AI scoring agents.</DialogDescription>
               </div>
            </div>
          </DialogHeader>

          <div className="relative z-10 flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain px-4 py-6 sm:px-6 sm:py-8 md:overflow-hidden">
            <div className="grid grid-cols-1 gap-8 animate-in fade-in zoom-in-95 duration-300 md:min-h-0 md:flex-1 md:grid-cols-5">
              <div className="flex flex-col gap-4 md:col-span-3 md:min-h-0">
                <div className="flex items-center justify-between">
                  <Label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground whitespace-nowrap">
                    Execution Strategy {selectedSources.length > 0 && `(${selectedSources.length})`}
                  </Label>
                  <button 
                    onClick={() => {
                      if (selectedSources.length > 0) selectNone();
                      else selectAll();
                    }}
                    className="text-[10px] font-bold text-primary/80 hover:text-primary transition-all flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-primary/5 border border-transparent hover:border-primary/10"
                  >
                    {selectedSources.length > 0 ? (
                      <>Deselect All</>
                    ) : (
                      <>Select All</>
                    )}
                  </button>
                </div>
                <div className="flex flex-col gap-2 md:min-h-0 md:overflow-y-auto md:pr-2">
                  {providers.map((option) => (
                    <div
                      key={option.name}
                      onClick={() => toggleSource(option.name)}
                      className={`flex items-center justify-between p-4 rounded-xl border transition-all text-left group cursor-pointer ${
                        selectedSources.includes(option.name)
                          ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20'
                          : 'border-border/50 hover:border-border hover:bg-muted/30'
                      }`}
                    >
                      <div className="flex flex-col grow pr-4">
                        <div className={`text-sm font-bold flex items-center gap-1.5 w-full ${selectedSources.includes(option.name) ? 'text-primary' : ''}`}>
                          {option.display_name}
                          {option.shows_aggregator_badge && aggregatorStatus && (
                            <div className="ml-auto">
                              {aggregatorStatus.is_up_to_date ? (
                                <Badge variant="outline" className="text-[9px] bg-emerald-500/5 text-emerald-500 border-emerald-500/20 py-0 h-4">Up to Date</Badge>
                              ) : (
                                <Badge variant="outline" className="text-[9px] bg-amber-500/5 text-amber-500 border-amber-500/20 py-0 h-4 shadow-sm animate-pulse">New Data Available</Badge>
                              )}
                            </div>
                          )}
                        </div>
                        <span className="text-[10px] text-muted-foreground mt-1 leading-normal">
                          {option.name === 'aggregator' && aggregatorStatus
                            ? `Broad Market: Scans ${aggregatorStatus.total_jobs.toLocaleString()} jobs from the open aggregator.`
                            : option.description}
                        </span>
                      </div>
                      <div className={`h-4 w-4 shrink-0 rounded border transition-all flex items-center justify-center ${
                        selectedSources.includes(option.name) 
                          ? 'bg-primary border-primary scale-110 shadow-sm' 
                          : 'bg-transparent border-border scale-100'
                      }`}>
                         {selectedSources.includes(option.name) && (
                           <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={4}>
                             <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                           </svg>
                         )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-6 md:col-span-2">
                <div className="space-y-4">
                  <Label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Run Type</Label>
                  <div className="flex flex-col gap-2">
                    <div
                      onClick={() => setDryRun(false)}
                      className={`flex items-center justify-between p-4 rounded-xl border transition-all text-left cursor-pointer ${
                        !dryRun
                          ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20'
                          : 'border-border/50 hover:border-border hover:bg-muted/30'
                      }`}
                    >
                      <div className="flex flex-col">
                        <span className={`text-sm font-bold ${!dryRun ? 'text-primary' : ''}`}>Intelligence Pass</span>
                        <span className="text-[10px] text-muted-foreground mt-0.5">AI scoring · uses API credits</span>
                      </div>
                      <div className={`h-2 w-2 rounded-full transition-all ${!dryRun ? 'bg-primary scale-125' : 'bg-muted scale-100'}`} />
                    </div>
                    <div
                      onClick={() => setDryRun(true)}
                      className={`flex items-center justify-between p-4 rounded-xl border transition-all text-left cursor-pointer ${
                        dryRun
                          ? 'border-emerald-500/40 bg-emerald-500/5 shadow-sm ring-1 ring-emerald-500/20'
                          : 'border-border/50 hover:border-border hover:bg-muted/30'
                      }`}
                    >
                      <div className="flex flex-col">
                        <span className={`text-sm font-bold ${dryRun ? 'text-emerald-500' : ''}`}>Dry Run</span>
                        <span className="text-[10px] text-muted-foreground mt-0.5">No LLM calls · free</span>
                      </div>
                      <div className={`h-2 w-2 rounded-full transition-all ${dryRun ? 'bg-emerald-500 scale-125' : 'bg-muted scale-100'}`} />
                    </div>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-primary/5 border border-primary/10 flex gap-3 text-xs text-muted-foreground leading-relaxed">
                   <Info className="h-4 w-4 text-primary shrink-0" />
                   <p>Launching the pipeline will trigger background Python subprocesses. You can safely close this dialog while it runs.</p>
                </div>
                { selectedSources.includes('remotive') && (
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 flex gap-2.5 text-[10px] text-amber-600 dark:text-amber-400 leading-tight animate-in slide-in-from-top-2 duration-300">
                    <Info className="h-3.5 w-3.5 shrink-0" />
                    <p><span className="font-bold">Remotive Note:</span> The public API is limited to the 20 most recent jobs.</p>
                  </div>
                )}
                { selectedSources.includes('remoteok') && (
                  <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 flex gap-2.5 text-[10px] text-blue-600 dark:text-blue-400 leading-tight animate-in slide-in-from-top-2 duration-300">
                    <Info className="h-3.5 w-3.5 shrink-0" />
                    <p><span className="font-bold">Remote OK:</span> Fetches current remote listings (~50-100 items).</p>
                  </div>
                )}
              </div>
            </div>

            <div className="shrink-0 space-y-3 pt-8">
              <Button onClick={handleStart} disabled={isStarting || selectedSources.length === 0} className="w-full h-14 text-lg font-bold gap-3 shadow-xl hover:scale-[1.01] active:scale-[0.99] transition-all">
                {isStarting ? <Loader2 className="h-5 w-5 animate-spin" /> : <Play className="h-5 w-5 fill-current" />}
                {selectedSources.length === 0 ? 'Select a source' : (dryRun ? 'Start Dry Run' : 'Start Intelligence Pass')}
              </Button>
              {activeRun?.running && (
                <Button onClick={() => setShowProgress(true)} variant="outline" className="w-full gap-2 italic">
                  <Terminal className="h-4 w-4" /> View active progress logs
                </Button>
              )}
            </div>
          </div>

          <DialogFooter className="relative z-10 mx-0 mb-0 mt-auto shrink-0 rounded-none border-t border-border/50 px-4 py-4 text-[10px] text-muted-foreground sm:px-6">
            <div className="flex items-center gap-2">
               <History className="h-3 w-3" />
               Selected: {selectedSources.length} source(s)
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PipelineProgressDialog
        runId={activeRun?.run_id || null}
        open={showProgress}
        onOpenChange={setShowProgress}
        onComplete={() => {
          fetchActive()
          window.dispatchEvent(new Event('pipeline-finished'))
        }}
      />
    </>
  )
}
