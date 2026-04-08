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
  Save, 
  RefreshCw, 
  FileCode, 
  FileText, 
  ChevronLeft,
  Check,
  AlertCircle,
  BrainCircuit,
  Info
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api/client'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

import { StepProps } from '../types'

export function ReviewGenerate({ onNext, onBack, onUpdate, data }: StepProps) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [yamlContent, setYamlContent] = useState('')
  const [mdContent, setMdContent] = useState('')
  const [activeTab, setActiveTab] = useState('doc')
  const [refineStatus, setRefineStatus] = useState<'idle' | 'refining' | 'done'>('idle')
  const [changesMade, setChangesMade] = useState<string[]>([])

  const generateProfile = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (data?.path === 'manual') {
        const response = await api.GET('/api/wizard/template')
        if ((response as any).error) {
          const detail = (response.error as any)?.detail || 'Failed to fetch template'
          throw new Error(typeof detail === 'string' ? detail : 'Failed to fetch template')
        }
        setYamlContent((response as any).data?.profile_yaml || '')
        setMdContent((response as any).data?.profile_doc || '')
        return
      }

      const user_preferences = {
        targetRoles: data.targetRoles || [],
        seniority: data.seniority || 'senior',
        location: data.location || '',
        workAuth: data.workAuth || '',
        remotePref: data.remotePref || ['remote'],
        primaryRemotePref: data.primaryRemotePref || 'remote',
        timezonePref: data.timezonePref || 'local',
        targetRegions: data.targetRegions || ['Europe'],
        excludedRegions: data.excludedRegions || [],
        industries: data.industries || [],
        careerDirection: data.careerDirection || '',
        goodMatchSignals: data.goodMatchSignals || [],
        dealBreakers: data.dealBreakers || [],
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

      setYamlContent(response.data.profile_yaml)
      setMdContent(response.data.profile_doc)

      // Second pass: refine with LLM (non-blocking — if it fails, we keep template output)
      try {
        setRefineStatus('refining')
        const refineRes = await (api as any).POST('/api/wizard/refine-profile', {
          body: {
            cv_analysis: data.cvAnalysis,
            user_preferences: {
              targetRoles: data.targetRoles || [],
              seniority: data.seniority || [],
              location: data.location || '',
              workAuth: data.workAuth || '',
              remotePref: data.remotePref || [],
              primaryRemotePref: data.primaryRemotePref || '',
              timezonePref: data.timezonePref || '',
              targetRegions: data.targetRegions || [],
              excludedRegions: data.excludedRegions || [],
              industries: data.industries || [],
              careerDirection: data.careerDirection || '',
              careerGoal: data.careerGoal || 'stay',
              goodMatchSignals: data.goodMatchSignals || [],
              dealBreakers: data.dealBreakers || [],
              enableStandardExclusions: data.enableStandardExclusions ?? true,
              additionalContext: data.additionalContext || '',
            },
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

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-6 animate-in fade-in duration-700">
        <div className="relative">
          <div className="absolute inset-0 bg-primary/20 blur-2xl rounded-full animate-pulse px-8 py-8" />
          <div className="relative bg-background/50 border border-primary/20 p-6 rounded-3xl shadow-2xl">
            <BrainCircuit className="h-12 w-12 text-primary animate-[spin_3s_linear_infinite]" />
          </div>
        </div>
        <div className="space-y-1 bg-background/50 py-4 -mt-6 border-b border-border/10 w-full">
            <h2 className="text-2xl font-bold tracking-tight">
              {data?.path === 'manual' ? 'Loading Template' : 'Generating Profile'}
            </h2>
            <p className="text-muted-foreground text-xs leading-relaxed px-4 max-w-xs mx-auto">
              {data?.path === 'manual' 
                ? 'Preparing your manual setup environment...' 
                : refineStatus === 'refining'
                  ? 'Polishing your profile with AI...'
                  : 'Generating your job matching profile...'}
            </p>
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
          <details className="p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-2xl text-xs">
            <summary className="font-bold text-emerald-600 cursor-pointer">
              AI Refinement: {changesMade.length} improvements applied
            </summary>
            <ul className="mt-2 space-y-1 text-muted-foreground">
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
                <CardTitle className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/70">profile_doc.md</CardTitle>
                <div className="flex gap-2">
                   <Badge variant="outline" className={cn(
                     "h-5 text-[9px] font-mono border-emerald-500/30 text-emerald-500/80 bg-emerald-500/5 px-2",
                     data?.path === 'manual' && "border-blue-500/30 text-blue-500/80 bg-blue-500/5"
                   )}>
                     {data?.path === 'manual' ? 'Template' : 'Generated'}
                   </Badge>
                   <Badge variant="outline" className="h-5 text-[9px] font-mono opacity-50 px-2">
                     {data?.path === 'manual' ? 'Customizable' : 'Editable'}
                   </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <textarea
                  className="w-full min-h-[400px] p-6 bg-transparent resize-none font-mono text-sm leading-relaxed focus:outline-none focus:ring-1 focus:ring-primary/20 transition-all scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent"
                  value={mdContent}
                  onChange={(e) => setMdContent(e.target.value)}
                  spellCheck={false}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="rules" className="mt-0 animate-in fade-in slide-in-from-right-4 duration-300">
            <Card className="border-border/50 bg-background/40 backdrop-blur-md overflow-hidden shadow-sm rounded-3xl">
              <CardHeader className="py-2.5 px-4 bg-muted/20 border-b border-border/20 flex flex-row items-center justify-between">
                <CardTitle className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/70">search_config.yaml</CardTitle>
                <div className="flex gap-2">
                   <Badge variant="outline" className={cn(
                     "h-5 text-[9px] font-mono border-emerald-500/30 text-emerald-500/80 bg-emerald-500/5 px-2",
                     data?.path === 'manual' && "border-blue-500/30 text-blue-500/80 bg-blue-500/5"
                   )}>
                     {data?.path === 'manual' ? 'Template' : 'Generated'}
                   </Badge>
                   <Badge variant="outline" className="h-5 text-[9px] font-mono opacity-50 px-2">
                     {data?.path === 'manual' ? 'Customizable' : 'Editable'}
                   </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <textarea
                  className="w-full min-h-[400px] p-6 bg-transparent resize-none font-mono text-sm leading-relaxed focus:outline-none focus:ring-1 focus:ring-primary/20 transition-all scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent"
                  value={yamlContent}
                  onChange={(e) => setYamlContent(e.target.value)}
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
