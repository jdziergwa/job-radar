'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { 
  Tabs, 
  TabsContent, 
  TabsList, 
  TabsTrigger 
} from '@/components/ui/tabs'
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card'
import { 
  Loader2, 
  RefreshCw, 
  FileCode, 
  FileText, 
  ChevronLeft,
  Check,
  AlertCircle,
  BrainCircuit,
  Info,
  Sparkles
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api/client'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

import { DEFAULT_TIMEZONE_PREF, StepProps, normalizeTimezonePref } from '../types'

const PROFILE_GENERATION_MESSAGES = [
  { icon: BrainCircuit, text: 'Building your first draft...' },
  { icon: FileText, text: 'Turning your inputs into profile guidance...' },
  { icon: FileCode, text: 'Preparing matching rules and constraints...' },
  { icon: Sparkles, text: 'Polishing the generated profile...' },
]

const TEMPLATE_LOADING_MESSAGES = [
  { icon: FileText, text: 'Loading the starter profile...' },
  { icon: FileCode, text: 'Preparing editable matching rules...' },
  { icon: Sparkles, text: 'Getting your manual setup workspace ready...' },
]

export function ReviewGenerate({ onNext, onBack, onUpdate, data }: StepProps) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [starterYamlContent, setStarterYamlContent] = useState('')
  const [starterMdContent, setStarterMdContent] = useState('')
  const [yamlContent, setYamlContent] = useState('')
  const [mdContent, setMdContent] = useState('')
  const [activeTab, setActiveTab] = useState('doc')
  const [versionTab, setVersionTab] = useState<'refined' | 'starter'>('refined')
  const [refineStatus, setRefineStatus] = useState<'idle' | 'refining' | 'done'>('idle')
  const [changesMade, setChangesMade] = useState<string[]>([])
  const [msgIndex, setMsgIndex] = useState(0)

  const loadingMessages = data?.path === 'manual' ? TEMPLATE_LOADING_MESSAGES : PROFILE_GENERATION_MESSAGES

  const generateProfile = useCallback(async () => {
    setLoading(true)
    setError(null)
    setChangesMade([])
    setRefineStatus('idle')
    try {
      if (data?.path === 'manual') {
        const response = await api.GET('/api/wizard/template')
        if ((response as any).error) {
          const detail = (response.error as any)?.detail || 'Failed to fetch template'
          throw new Error(typeof detail === 'string' ? detail : 'Failed to fetch template')
        }
        const templateYaml = (response as any).data?.profile_yaml || ''
        const templateDoc = (response as any).data?.profile_doc || ''
        setStarterYamlContent('')
        setStarterMdContent('')
        setYamlContent(templateYaml)
        setMdContent(templateDoc)
        setVersionTab('refined')
        return
      }

      const user_preferences = {
        targetRoles: data.targetRoles || [],
        seniority: data.seniority || [],
        baseCity: data.baseCity || '',
        baseCountry: data.baseCountry || '',
        location: data.location || [data.baseCity, data.baseCountry].filter(Boolean).join(', '),
        workAuth: data.workAuth || '',
        remotePref: data.remotePref || ['remote'],
        primaryRemotePref: data.primaryRemotePref || 'remote',
        timezonePref: normalizeTimezonePref(data.timezonePref) || DEFAULT_TIMEZONE_PREF,
        targetRegions: data.targetRegions || ['Europe'],
        excludedRegions: data.excludedRegions || [],
        industries: data.industries || [],
        careerDirection: data.careerDirection || '',
        careerGoal: data.careerGoal || 'stay',
        careerDirectionEdited: data.careerDirectionEdited ?? false,
        goodMatchSignals: data.goodMatchSignals || [],
        goodMatchSignalsConfirmed: data.goodMatchSignalsConfirmed ?? false,
        companyQualitySignals: data.companyQualitySignals || [],
        allowLowerSeniorityAtStrategicCompanies: (data.companyQualitySignals?.length ?? 0) > 0,
        dealBreakers: data.dealBreakers || [],
        dealBreakersConfirmed: data.dealBreakersConfirmed ?? false,
        enableStandardExclusions: data.enableStandardExclusions ?? true,
        additionalContext: data.additionalContext || ''
      }

      const response = await api.POST('/api/wizard/generate-profile', {
        body: {
          cv_analysis: data.cvAnalysis as any,
          user_preferences: user_preferences as any,
          profile_name: 'default'
        }
      })

      if (response.error) {
        const detail = (response.error as any)?.detail || 'Failed to generate profile'
        throw new Error(typeof detail === 'string' ? detail : 'Failed to generate profile')
      }

      setStarterYamlContent(response.data.profile_yaml)
      setStarterMdContent(response.data.profile_doc)
      setYamlContent(response.data.profile_yaml)
      setMdContent(response.data.profile_doc)
      setVersionTab('refined')

      // Second pass: refine with LLM (non-blocking — if it fails, we keep template output)
      try {
        setRefineStatus('refining')
        const refineRes = await (api as any).POST('/api/wizard/refine-profile', {
          body: {
            cv_analysis: data.cvAnalysis,
            user_preferences: user_preferences as any,
            draft_doc: response.data.profile_doc,
            draft_yaml: response.data.profile_yaml,
          }
        })
        if (refineRes.data) {
          setYamlContent(refineRes.data.profile_yaml)
          setMdContent(refineRes.data.profile_doc)
          setChangesMade(refineRes.data.changes_made || [])
        }
      } catch (refineErr) {
        console.warn('Refinement failed, using template output:', refineErr)
      } finally {
        setRefineStatus('done')
      }
    } catch (err: any) {
      console.error(err)
      setError(err.message || 'An unexpected error occurred during generation')
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    generateProfile()
  }, [generateProfile])

  useEffect(() => {
    if (!loading) return

    const interval = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % loadingMessages.length)
    }, 2800)

    return () => clearInterval(interval)
  }, [loading, loadingMessages.length])

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await api.POST('/api/wizard/save-profile', {
        body: {
          profile_name: 'default',
          profile_yaml: yamlContent,
          profile_doc: mdContent
        }
      })

      if (response.error) {
        const detail = (response.error as any)?.detail || 'Failed to save profile'
        throw new Error(typeof detail === 'string' ? detail : 'Failed to save profile')
      }

      toast.success('Profile saved successfully!')
      onNext({ completed: true })
    } catch (err: any) {
      toast.error(err.message || 'Failed to save profile')
    } finally {
      setSaving(false)
    }
  }

  const isGuidedFlow = data?.path !== 'manual'
  const isStarterView = isGuidedFlow && versionTab === 'starter'
  const visibleDocContent = isStarterView ? starterMdContent : mdContent
  const visibleYamlContent = isStarterView ? starterYamlContent : yamlContent

  if (loading) {
    const headline = data?.path === 'manual' ? 'Loading Template' : 'Generating Profile'
    const statusText = data?.path === 'manual'
      ? 'Preparing your manual setup workspace.'
      : refineStatus === 'refining'
        ? 'Polishing your profile with AI. This usually takes a moment.'
        : 'Building your first draft from the wizard inputs and CV analysis.'
    const StepIcon = loadingMessages[msgIndex].icon

    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-10 py-12 animate-in fade-in duration-700">
        <div className="relative">
          <div className="absolute inset-0 bg-primary/20 blur-[100px] rounded-full scale-150 animate-pulse" />

          <div className="relative bg-background/40 backdrop-blur-xl border border-primary/20 rounded-[2.5rem] p-12 shadow-2xl flex items-center justify-center overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-tr from-primary/10 via-transparent to-primary/5 opacity-50" />
            <Loader2 className="h-16 w-16 animate-spin text-primary relative z-10" />
            <div className="absolute inset-0 border-2 border-primary/10 rounded-[2.5rem] animate-[spin_10s_linear_infinite]" />
          </div>
        </div>

        <div className="text-center space-y-6 max-w-sm relative z-10">
          <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary font-bold uppercase tracking-widest text-[10px] shadow-sm">
            <StepIcon className="h-3.5 w-3.5 animate-bounce" />
            <span className="animate-in slide-in-from-bottom-2 duration-500 min-w-[220px]" key={`${data?.path ?? 'guided'}-${msgIndex}`}>
              {loadingMessages[msgIndex].text}
            </span>
          </div>

          <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight">{headline}</h2>
            <p className="text-muted-foreground text-xs leading-relaxed px-4 max-w-xs mx-auto">
              {statusText}
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          {loadingMessages.map((_, i) => (
            <div
              key={i}
              className={cn(
                'h-1.5 rounded-full transition-all duration-1000',
                i === msgIndex ? 'bg-primary w-8' : 'bg-primary/20 w-1.5'
              )}
            />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-6 text-center animate-in fade-in zoom-in-95">
        <div className="bg-destructive/10 p-4 rounded-full border border-destructive/20">
          <AlertCircle className="h-10 w-10 text-destructive" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-bold">Generation Failed</h2>
          <p className="text-muted-foreground text-sm max-w-sm">{error}</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={generateProfile} variant="default" className="gap-2">
            <RefreshCw className="h-4 w-4" /> Try Again
          </Button>
          <Button onClick={() => onBack()} variant="outline">Back</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 py-4 animate-in fade-in slide-in-from-bottom-8 duration-700 max-w-5xl mx-auto w-full">
      <div className="text-center space-y-1 bg-background/50 py-6 -mt-4 border-b border-border/20 mb-4">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">
          {data?.path === 'manual' ? 'Manual Setup' : 'Review & Finalize'}
        </h2>
        <p className="text-muted-foreground text-sm max-w-sm mx-auto">
          {data?.path === 'manual' 
            ? 'Start with a template and customize your matching rules and profile.' 
            : 'Your AI-generated job matching profile is ready for a quick check.'}
        </p>
      </div>

      <div className="flex flex-col gap-4">
        {changesMade.length > 0 && (
          <details className="px-4 py-3 bg-emerald-500/5 border border-emerald-500/20 rounded-2xl text-xs">
            <summary className="font-bold text-emerald-600 cursor-pointer list-none">
              <span className="inline-flex items-center gap-2">
                <Sparkles className="size-3.5" />
                AI refinement applied {changesMade.length} improvements
              </span>
            </summary>
            <ul className="mt-3 space-y-1 text-muted-foreground">
              {changesMade.map((change, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-emerald-500 shrink-0">-</span>
                  {change}
                </li>
              ))}
            </ul>
          </details>
        )}
        <Tabs defaultValue="doc" className="w-full" onValueChange={setActiveTab}>
          <div className="flex items-center justify-between mb-4">
            <TabsList className="bg-muted/30 p-1 border border-border/50 h-10">
              <TabsTrigger value="doc" className="gap-2 px-4">
                <FileText className="size-3.5" />
                Profile Doc
              </TabsTrigger>
              <TabsTrigger value="rules" className="gap-2 px-4">
                <FileCode className="size-3.5" />
                Matching Rules
              </TabsTrigger>
            </TabsList>

            <Button 
              variant="ghost" 
              size="sm" 
              onClick={generateProfile}
              className="h-8 text-xs gap-1.5 text-muted-foreground hover:text-foreground"
            >
              <RefreshCw className="size-3" />
              {data?.path === 'manual' ? 'Reset Template' : 'Regenerate'}
            </Button>
          </div>

          <TabsContent value="doc" className="mt-0 animate-in fade-in slide-in-from-right-4 duration-300">
            <Card className="border-border/50 bg-background/40 backdrop-blur-md overflow-hidden shadow-sm rounded-3xl">
              <CardHeader className="py-2.5 px-4 bg-muted/20 border-b border-border/20 flex flex-row items-center justify-between">
                <div className="flex items-center gap-3">
                  <CardTitle className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/70">profile_doc.md</CardTitle>
                  {isGuidedFlow && (
                    <div className="inline-flex items-center rounded-xl border border-border/50 bg-background/60 p-1">
                      <button
                        type="button"
                        onClick={() => setVersionTab('refined')}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-medium transition-colors",
                          !isStarterView
                            ? "bg-emerald-500/10 text-emerald-500"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <Sparkles className="size-3" />
                        AI Refined
                      </button>
                      <button
                        type="button"
                        onClick={() => setVersionTab('starter')}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-medium transition-colors",
                          isStarterView
                            ? "bg-muted text-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <FileText className="size-3" />
                        Starter Draft
                      </button>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                   <Badge variant="outline" className={cn(
                     "h-5 text-[9px] font-mono px-2",
                     isStarterView
                       ? "border-border/40 text-muted-foreground bg-muted/20"
                       : data?.path === 'manual'
                         ? "border-blue-500/30 text-blue-500/80 bg-blue-500/5"
                         : "border-emerald-500/30 text-emerald-500/80 bg-emerald-500/5"
                   )}>
                     {isStarterView ? 'Reference Only' : data?.path === 'manual' ? 'Template' : 'Used For Matching'}
                   </Badge>
                   <Badge variant="outline" className="h-5 text-[9px] font-mono opacity-50 px-2">
                     {isStarterView ? 'Read Only' : data?.path === 'manual' ? 'Customizable' : 'Editable'}
                   </Badge>
                </div>
              </CardHeader>
              {isGuidedFlow && (
                <div className="px-4 py-2.5 text-[11px] text-muted-foreground border-b border-border/20">
                  {isStarterView
                    ? 'Reference baseline for cross-checking.'
                    : 'Primary editable version used for matching.'}
                </div>
              )}
              <CardContent className="p-0">
                <textarea
                  className={cn(
                    "w-full min-h-[400px] p-6 resize-none font-mono text-sm leading-relaxed transition-all scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent",
                    isStarterView
                      ? "bg-muted/10 text-muted-foreground/90 focus:outline-none"
                      : "bg-transparent focus:outline-none focus:ring-1 focus:ring-primary/20"
                  )}
                  value={visibleDocContent}
                  onChange={(e) => {
                    if (!isStarterView) setMdContent(e.target.value)
                  }}
                  readOnly={isStarterView}
                  spellCheck={false}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="rules" className="mt-0 animate-in fade-in slide-in-from-right-4 duration-300">
            <Card className="border-border/50 bg-background/40 backdrop-blur-md overflow-hidden shadow-sm rounded-3xl">
              <CardHeader className="py-2.5 px-4 bg-muted/20 border-b border-border/20 flex flex-row items-center justify-between">
                <div className="flex items-center gap-3">
                  <CardTitle className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/70">search_config.yaml</CardTitle>
                  {isGuidedFlow && (
                    <div className="inline-flex items-center rounded-xl border border-border/50 bg-background/60 p-1">
                      <button
                        type="button"
                        onClick={() => setVersionTab('refined')}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-medium transition-colors",
                          !isStarterView
                            ? "bg-emerald-500/10 text-emerald-500"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <Sparkles className="size-3" />
                        AI Refined
                      </button>
                      <button
                        type="button"
                        onClick={() => setVersionTab('starter')}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-medium transition-colors",
                          isStarterView
                            ? "bg-muted text-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <FileText className="size-3" />
                        Starter Draft
                      </button>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                   <Badge variant="outline" className={cn(
                     "h-5 text-[9px] font-mono px-2",
                     isStarterView
                       ? "border-border/40 text-muted-foreground bg-muted/20"
                       : data?.path === 'manual'
                         ? "border-blue-500/30 text-blue-500/80 bg-blue-500/5"
                         : "border-emerald-500/30 text-emerald-500/80 bg-emerald-500/5"
                   )}>
                     {isStarterView ? 'Reference Only' : data?.path === 'manual' ? 'Template' : 'Used For Matching'}
                   </Badge>
                   <Badge variant="outline" className="h-5 text-[9px] font-mono opacity-50 px-2">
                     {isStarterView ? 'Read Only' : data?.path === 'manual' ? 'Customizable' : 'Editable'}
                   </Badge>
                </div>
              </CardHeader>
              {isGuidedFlow && (
                <div className="px-4 py-2.5 text-[11px] text-muted-foreground border-b border-border/20">
                  {isStarterView
                    ? 'Reference baseline for cross-checking.'
                    : 'Primary editable version used for matching.'}
                </div>
              )}
              <CardContent className="p-0">
                <textarea
                  className={cn(
                    "w-full min-h-[400px] p-6 resize-none font-mono text-sm leading-relaxed transition-all scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent",
                    isStarterView
                      ? "bg-muted/10 text-muted-foreground/90 focus:outline-none"
                      : "bg-transparent focus:outline-none focus:ring-1 focus:ring-primary/20"
                  )}
                  value={visibleYamlContent}
                  onChange={(e) => {
                    if (!isStarterView) setYamlContent(e.target.value)
                  }}
                  readOnly={isStarterView}
                  spellCheck={false}
                />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="p-4 bg-primary/5 border border-primary/10 rounded-2xl flex gap-3 text-xs text-muted-foreground/80 leading-relaxed shadow-sm">
          <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" />
          <p>
            Scoring philosophy (how dimensions like tech stack or seniority are weighted) uses sensible defaults.
            You can customize these later in <span className="text-primary font-medium">Settings</span> to fine-tune your results.
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-border/20">
        <Button 
          onClick={handleSave}
          disabled={saving}
          className="w-full sm:flex-[2] h-14 text-lg font-bold shadow-xl gap-2 rounded-2xl hover:scale-[1.01] transition-all bg-primary hover:bg-primary/90"
        >
          {saving ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Saving Profile...
            </>
          ) : (
            <>
              Save & Finish
              <Check className="h-5 w-5" />
            </>
          )}
        </Button>
        <Button 
          onClick={() => onBack()} 
          variant="outline" 
          disabled={saving}
          className="w-full sm:flex-1 h-14 text-base rounded-2xl border-border/50 hover:bg-muted/30 gap-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Back
        </Button>
      </div>
    </div>
  )
}
