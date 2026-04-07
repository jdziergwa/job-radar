'use client'

import React, { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
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
import { Button } from '@/components/ui/button'
import { 
  Save, 
  FileCode, 
  FileText, 
  Settings2, 
  Loader2, 
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  BrainCircuit,
  RefreshCw
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export default function SettingsPage() {
  const [yamlContent, setYamlContent] = useState('')
  const [docContent, setDocContent] = useState('')
  const [philosophyContent, setPhilosophyContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [yamlError, setYamlError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('rules')

  const fetchProfileData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [yamlRes, docRes, philosophyRes] = await Promise.all([
        api.GET('/api/profile/{name}/yaml', {
          params: { path: { name: 'default' } }
        }),
        api.GET('/api/profile/{name}/doc', {
          params: { path: { name: 'default' } }
        }),
        api.GET('/api/profile/{name}/scoring-philosophy', {
          params: { path: { name: 'default' } }
        }),
      ])

      if (yamlRes.error) throw new Error('Failed to fetch YAML rules')
      if (docRes.error) throw new Error('Failed to fetch resume document')
      if (philosophyRes.error) throw new Error('Failed to fetch scoring philosophy')

      setYamlContent((yamlRes.data as any).content)
      setDocContent((docRes.data as any).content)
      setPhilosophyContent((philosophyRes.data as any).content)
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProfileData()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSuccess(null)
    setYamlError(null)

    try {
      if (activeTab === 'rules') {
        const { error: apiError, response } = await api.PUT('/api/profile/{name}/yaml', {
          params: { path: { name: 'default' } },
          body: { content: yamlContent }
        })
        
        if (response.status === 422) {
          const detail = (await response.json())?.detail
          setYamlError(detail || 'Invalid YAML syntax')
          throw new Error('YAML syntax validation failed')
        }
        
        if (apiError) throw new Error('Failed to save rules')
      } else if (activeTab === 'resume') {
        const { error: apiError } = await api.PUT('/api/profile/{name}/doc', {
          params: { path: { name: 'default' } },
          body: { content: docContent }
        })
        if (apiError) throw new Error('Failed to save resume')
      } else if (activeTab === 'philosophy') {
        const { error: apiError, response } = await api.PUT('/api/profile/{name}/scoring-philosophy', {
          params: { path: { name: 'default' } },
          body: { content: philosophyContent }
        })
        if (response.status === 422) {
          const detail = (await response.json())?.detail
          setYamlError(detail || 'Validation error')
          throw new Error('Validation failed')
        }
        if (apiError) throw new Error('Failed to save scoring philosophy')
      }

      const tabLabels: Record<string, string> = {
        rules: 'matching rules',
        resume: 'resume',
        philosophy: 'scoring philosophy',
      }
      setSuccess(`Changes to ${tabLabels[activeTab]} saved successfully.`)
      setTimeout(() => setSuccess(null), 3000)
    } catch (err: any) {
      if (err.message !== 'YAML syntax validation failed' && err.message !== 'Validation failed') {
        setError(err.message || 'Internal saving error')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col bg-background/30 px-6 py-8 animate-in fade-in duration-700">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Settings2 className="h-5 w-5 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 font-mono">Profile Config</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
          <p className="text-muted-foreground mt-1 text-sm max-w-2xl">
            Fine-tune your job matching logic, personalize your resume context, and configure the AI scoring prompt.
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {success && (
            <div className="flex items-center gap-2 text-emerald-500 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20 text-xs font-medium animate-in slide-in-from-right-4">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {success}
            </div>
          )}
          <Button 
            onClick={handleSave} 
            disabled={saving || loading}
            className="gap-2 bg-primary/90 hover:bg-primary shadow-lg border-primary/20 min-w-[120px] transition-all duration-300"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Changes
          </Button>
        </div>
      </header>

      {loading ? (
        <div className="flex flex-col items-center justify-center p-32 gap-4 text-muted-foreground">
          <Loader2 className="h-10 w-10 animate-spin text-primary" />
          <p className="animate-pulse font-medium">Loading profile configurations...</p>
        </div>
      ) : error && !yamlError ? (
        <div className="flex flex-col items-center justify-center p-32 gap-4 text-center">
          <div className="bg-destructive/10 p-4 rounded-full">
            <AlertCircle className="h-10 w-10 text-destructive" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Failed to Load Control Panel</h2>
            <p className="text-muted-foreground text-sm max-w-sm">{error}</p>
          </div>
          <Button onClick={fetchProfileData} variant="outline" size="sm">Try Again</Button>
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-6">
          <Tabs defaultValue="rules" className="w-full flex-1 flex flex-col" onValueChange={setActiveTab}>
            <TabsList className="bg-muted/30 p-1 border border-border/50 mb-6 h-12 self-start">
              <TabsTrigger 
                value="rules" 
                className="px-5 data-[state=active]:bg-background/60 data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all duration-300 gap-2"
              >
                <FileCode className="h-4 w-4" />
                Matching Rules (YAML)
              </TabsTrigger>
              <TabsTrigger 
                value="resume" 
                className="px-5 data-[state=active]:bg-background/60 data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all duration-300 gap-2"
              >
                <FileText className="h-4 w-4" />
                Resume / CV (MD)
              </TabsTrigger>
              <TabsTrigger 
                value="philosophy" 
                className="px-5 data-[state=active]:bg-background/60 data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all duration-300 gap-2"
              >
                <BrainCircuit className="h-4 w-4" />
                Scoring Philosophy
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="rules" className="flex-1 min-h-0 animate-in fade-in slide-in-from-top-2 duration-300 overflow-hidden flex flex-col">
              {yamlError && (
                <div className="mb-4 bg-destructive/10 border border-destructive/20 p-4 rounded-xl flex gap-3 items-start animate-in zoom-in-95">
                  <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <h4 className="text-sm font-bold text-destructive">YAML Syntax Error</h4>
                    <p className="text-xs font-mono text-destructive/80 leading-relaxed whitespace-pre-wrap">{yamlError}</p>
                  </div>
                </div>
              )}
              <Card className="flex-1 border-border/50 bg-background/50 backdrop-blur-md overflow-hidden flex flex-col shadow-inner">
                <CardHeader className="py-3 bg-muted/20 border-b border-border/30">
                   <div className="flex justify-between items-center">
                      <CardTitle className="text-xs font-mono uppercase text-muted-foreground/80">profile.yaml</CardTitle>
                      <Badge variant="outline" className="text-[10px] font-mono opacity-60">Read/Write</Badge>
                   </div>
                </CardHeader>
                <CardContent className="p-0 flex-1 overflow-auto">
                   <textarea
                     className="w-full h-full min-h-[500px] p-6 bg-transparent resize-none font-mono text-sm leading-relaxed focus:outline-none scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent"
                     value={yamlContent}
                     onChange={(e) => setYamlContent(e.target.value)}
                     spellCheck={false}
                     placeholder="Enter your job search constraints in YAML format..."
                   />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="resume" className="flex-1 min-h-0 animate-in fade-in slide-in-from-top-2 duration-300 overflow-hidden flex flex-col">
              <Card className="flex-1 border-border/50 bg-background/50 backdrop-blur-md overflow-hidden flex flex-col shadow-inner">
                <CardHeader className="py-3 bg-muted/20 border-b border-border/30">
                   <div className="flex justify-between items-center">
                      <CardTitle className="text-xs font-mono uppercase text-muted-foreground/80">profile_doc.md</CardTitle>
                      <Badge variant="outline" className="text-[10px] font-mono opacity-60">Text/Markdown</Badge>
                   </div>
                </CardHeader>
                <CardContent className="p-0 flex-1 overflow-auto">
                   <textarea
                     className="w-full h-full min-h-[500px] p-6 bg-transparent resize-none font-mono text-sm leading-relaxed focus:outline-none scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent"
                     value={docContent}
                     onChange={(e) => setDocContent(e.target.value)}
                     spellCheck={false}
                     placeholder="Paste your resume or CV summary here for AI context injection..."
                   />
                </CardContent>
              </Card>
              <div className="mt-4 p-4 rounded-xl border border-primary/10 bg-primary/5 flex gap-3 text-xs text-muted-foreground">
                 <AlertCircle className="h-4 w-4 text-primary shrink-0" />
                 <p>This document is injected into the LLM prompt to measure the fit between your experience and the job description.</p>
              </div>
            </TabsContent>

            <TabsContent value="philosophy" className="flex-1 min-h-0 animate-in fade-in slide-in-from-top-2 duration-300 overflow-hidden flex flex-col">
              <Card className="flex-1 border-border/50 bg-background/50 backdrop-blur-md overflow-hidden flex flex-col shadow-inner">
                <CardHeader className="py-3 bg-muted/20 border-b border-border/30">
                   <div className="flex justify-between items-center">
                      <CardTitle className="text-xs font-mono uppercase text-muted-foreground/80">scoring_philosophy.md</CardTitle>
                      <Badge variant="outline" className="text-[10px] font-mono opacity-60">Plain Text</Badge>
                   </div>
                </CardHeader>
                <CardContent className="p-0 flex-1 overflow-auto">
                   <textarea
                     className="w-full h-full min-h-[500px] p-6 bg-transparent resize-none font-mono text-sm leading-relaxed focus:outline-none scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent"
                     value={philosophyContent}
                     onChange={(e) => setPhilosophyContent(e.target.value)}
                     spellCheck={false}
                     placeholder="Enter the scoring rubrics and philosophy..."
                   />
                </CardContent>
              </Card>
              <div className="mt-4 p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 flex gap-3 text-xs text-muted-foreground">
                 <RefreshCw className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                 <p>
                   This controls how the AI evaluates and weighs different aspects of job fit (tech stack matching, seniority, location, growth potential). The response format and JSON structure are fixed. Changes take effect on the next pipeline run.{' '}
                   <span className="text-amber-500/90 font-medium">Run &quot;Rescore All&quot; to apply changes to already-scored jobs.</span>
                 </p>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  )
}
