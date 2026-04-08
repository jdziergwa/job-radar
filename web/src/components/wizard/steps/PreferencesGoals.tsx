'use client'

import { useState, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { 
  Plus,
  X,
  ChevronLeft,
  ChevronRight,
  Compass,
  Trophy,
  Ban,
  MessageSquare,
  Building,
  User,
  Briefcase
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  COMPANY_QUALITY_SIGNAL_OPTIONS,
  dedupeCompanyQualitySignals,
  getCompanyQualitySignalLabel,
  normalizeCompanyQualitySignal,
} from '@/lib/company-quality'

import { StepProps } from '../types'

const INDUSTRIES = [
  'Fintech', 'SaaS', 'E-commerce', 'Healthcare', 'Gaming', 
  'Travel', 'IoT', 'Consulting', 'Crypto/Web3', 'Education', 
  'Media', 'Startup'
]

const EXCITEMENT_SIGNALS = [
  'Framework/tool ownership', 'Mentoring/leadership', 'Greenfield projects', 
  'Scale/high-traffic', 'Developer tooling', 'Open source', 'Research', 
  'Cross-team collaboration', 'Customer-facing', 'Strategic impact'
]

const DEAL_BREAKERS = [
  'Contract/agency roles', 'On-site required', 'Specific tech stacks', 
  'No growth path', 'Very large team', 'Very small team (<5)', 
  'Heavy on-call', 'Sales-heavy role'
]

export function PreferencesGoals({ onNext, onBack, onUpdate, data }: StepProps) {
  const analysis = data.cvAnalysis
  
  // Infer industries from experience if none selected
  const initialIndustries = useMemo(() => {
    if (data.industries && data.industries.length > 0) return data.industries
    if (!analysis?.experience) return []
    const inferred = analysis.experience
      .map(exp => exp.industry)
      .filter((ind): ind is string => !!ind)
    return [...new Set(inferred)]
  }, [data.industries, analysis?.experience])

  const [careerGoal, setCareerGoal] = useState<'stay' | 'pivot' | 'step_up' | 'broaden'>(
    (data.careerGoal as any) || 'stay'
  )
  const [careerDirection, setCareerDirection] = useState(
    data.careerDirection || 
    (analysis as any)?.suggested_narratives?.stay || 
    (analysis as any)?.suggested_career_direction || 
    ''
  )
  const [isManualEdit, setIsManualEdit] = useState(
    !!data.careerDirection && 
    data.careerDirection !== (analysis as any)?.suggested_narratives?.[careerGoal] &&
    data.careerDirection !== (analysis as any)?.suggested_career_direction
  )

  const [industries, setIndustries] = useState<string[]>(initialIndustries)
  const [goodMatchSignals, setGoodMatchSignals] = useState<string[]>(
    data.goodMatchSignals || analysis?.suggested_good_match_signals || []
  )
  const [companyQualitySignals, setCompanyQualitySignals] = useState<string[]>(
    dedupeCompanyQualitySignals(data.companyQualitySignals || [])
  )
  const [allowLowerSeniorityAtStrategicCompanies, setAllowLowerSeniorityAtStrategicCompanies] = useState(
    Boolean(data.allowLowerSeniorityAtStrategicCompanies && (data.companyQualitySignals || []).length > 0)
  )
  const [dealBreakers, setDealBreakers] = useState<string[]>(
    data.dealBreakers || analysis?.suggested_lower_fit_signals || []
  )
  const [additionalContext, setAdditionalContext] = useState(data.additionalContext || '')
  
  const [newIndustry, setNewIndustry] = useState('')
  const [newExcitement, setNewExcitement] = useState('')
  const [newCompanySignal, setNewCompanySignal] = useState('')
  const [newDealBreaker, setNewDealBreaker] = useState('')

  // Handle goal change with auto-drafting from LLM-generated narratives
  const handleGoalChange = (newGoal: 'stay' | 'pivot' | 'step_up' | 'broaden') => {
    setCareerGoal(newGoal)
    const suggestedNarratives = (analysis as any)?.suggested_narratives
    if (!isManualEdit && suggestedNarratives && suggestedNarratives[newGoal]) {
      setCareerDirection(suggestedNarratives[newGoal])
    }
  }

  // Auto-sync state back to wizardData for refresh resilience
  useEffect(() => {
    onUpdate({
      careerGoal,
      careerDirection,
      industries,
      goodMatchSignals,
      companyQualitySignals,
      allowLowerSeniorityAtStrategicCompanies,
      dealBreakers,
      additionalContext
    })
  }, [
    careerGoal,
    careerDirection,
    industries,
    goodMatchSignals,
    companyQualitySignals,
    allowLowerSeniorityAtStrategicCompanies,
    dealBreakers,
    additionalContext,
    onUpdate,
  ])

  useEffect(() => {
    if (companyQualitySignals.length === 0 && allowLowerSeniorityAtStrategicCompanies) {
      setAllowLowerSeniorityAtStrategicCompanies(false)
    }
  }, [companyQualitySignals, allowLowerSeniorityAtStrategicCompanies])

  const toggleItem = (item: string, list: string[], setter: (val: string[]) => void) => {
    if (list.includes(item)) {
      setter(list.filter(i => i !== item))
    } else {
      setter([...list, item])
    }
  }

  const handleAddItem = (
    value: string, 
    list: string[], 
    setter: (val: string[]) => void, 
    resetter: (val: string) => void
  ) => {
    const trimmed = value.trim()
    if (trimmed && !list.includes(trimmed)) {
      setter([...list, trimmed])
      resetter('')
    }
  }

  const toggleCompanySignal = (signal: string) => {
    const normalized = normalizeCompanyQualitySignal(signal)
    if (!normalized) return

    if (companyQualitySignals.includes(normalized)) {
      setCompanyQualitySignals(companyQualitySignals.filter((item) => item !== normalized))
      return
    }

    setCompanyQualitySignals(dedupeCompanyQualitySignals([...companyQualitySignals, normalized]))
  }

  const handleAddCompanySignal = () => {
    const normalized = normalizeCompanyQualitySignal(newCompanySignal)
    if (!normalized) return
    if (companyQualitySignals.includes(normalized)) {
      setNewCompanySignal('')
      return
    }

    setCompanyQualitySignals(dedupeCompanyQualitySignals([...companyQualitySignals, normalized]))
    setNewCompanySignal('')
  }

  // Dynamic option merges: Combine hardcoded defaults with unique AI suggestions
  const allIndustries = useMemo(() => {
    const aiIndustries = (analysis?.experience?.map(e => e.industry) || []).filter((i): i is string => !!i)
    return [...new Set([...INDUSTRIES, ...aiIndustries])]
  }, [analysis])

  const allExcitementOptions = useMemo(() => {
    const aiSigns = (analysis?.suggested_good_match_signals || []).filter((s): s is string => !!s)
    return [...new Set([...EXCITEMENT_SIGNALS, ...aiSigns])]
  }, [analysis])

  const allDealBreakerOptions = useMemo(() => {
    const aiLowFit = (analysis?.suggested_lower_fit_signals || []).filter((s): s is string => !!s)
    return [...new Set([...DEAL_BREAKERS, ...aiLowFit])]
  }, [analysis])

  const handleNext = () => {
    onNext({
      careerGoal,
      careerDirection,
      industries,
      goodMatchSignals,
      companyQualitySignals,
      allowLowerSeniorityAtStrategicCompanies,
      dealBreakers,
      additionalContext
    })
  }

  const GOAL_OPTIONS = [
    { id: 'stay', label: 'Stay on Track', icon: Briefcase, desc: 'Maintain current role and level' },
    { id: 'pivot', label: 'Pivot', icon: User, desc: 'Bridge experience to new role type' },
    { id: 'step_up', label: 'Step Up', icon: Trophy, desc: 'Lead, Management, or Strategic roles' },
    { id: 'broaden', label: 'Broaden', icon: Compass, desc: 'Expand into adjacent domains' },
  ]

  return (
    <div className="flex flex-col gap-8 py-4 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto w-full">
      <div className="text-center space-y-1 bg-background/50 py-6 -mt-4 border-b border-border/20 mb-4">
        <h2 className="text-2xl font-bold tracking-tight">Preferences & Goals</h2>
        <p className="text-muted-foreground text-sm max-w-sm mx-auto">Tell us about your career aspirations and boundaries.</p>
      </div>

      <div className="grid gap-5">
        {/* Career Goal Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-5 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <Compass className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground leading-tight">Refine your Career Direction</h3>
          </div>

          <div className="flex flex-col gap-4 pt-2">
            <label className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">
              Step 1: Choose a drafting preset
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {GOAL_OPTIONS.map((goal) => {
                const Icon = goal.icon
                const isActive = careerGoal === goal.id
                return (
                  <button
                    key={goal.id}
                    type="button"
                    onClick={() => handleGoalChange(goal.id as any)}
                    className={cn(
                      "flex flex-col gap-3 p-4 rounded-2xl border transition-all text-left group/card",
                      isActive 
                        ? "bg-primary/10 border-primary text-primary shadow-sm" 
                        : "bg-background/20 border-border/50 text-muted-foreground hover:bg-muted/30"
                    )}
                  >
                    <div className={cn(
                      "p-2 w-fit rounded-xl transition-colors",
                      isActive ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground group-hover/card:bg-primary/10 group-hover/card:text-primary"
                    )}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="font-bold text-sm leading-tight">{goal.label}</span>
                      <span className="text-[10px] opacity-70 leading-tight">{goal.desc}</span>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="flex flex-col gap-3 pt-6 border-t border-border/10 mt-2">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 ml-1">
                  <label className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 block">
                    Step 2: Finalize your narrative
                  </label>
                  {isManualEdit && (
                    <Badge variant="outline" className="text-[8px] h-4 px-1.5 border-amber-500/50 text-amber-500 bg-amber-500/5 transition-all">
                      Manual edits applied
                    </Badge>
                  )}
                </div>
                {(isManualEdit || careerDirection !== (analysis as any)?.suggested_narratives?.[careerGoal]) && (
                  <button 
                    onClick={() => {
                      const suggested = (analysis as any)?.suggested_narratives?.[careerGoal]
                      if (suggested) {
                        setCareerDirection(suggested)
                        setIsManualEdit(false)
                      }
                    }}
                    className="text-[10px] font-bold text-primary hover:underline flex items-center gap-1"
                  >
                    Reset to Preset
                  </button>
                )}
              </div>
              <div className="relative group/box">
                <Textarea 
                  value={careerDirection}
                  onChange={(e) => {
                    setCareerDirection(e.target.value)
                    setIsManualEdit(true)
                  }}
                  placeholder="e.g. My ideal next move is a Senior SDET role at a fintech company, focusing on infrastructure..."
                  className="min-h-[120px] bg-background/50 border-border/50 rounded-2xl p-4 text-sm leading-relaxed focus:bg-background/80 transition-all shadow-inner"
                />
                <div className="absolute top-4 right-4 text-muted-foreground/20 group-focus-within/box:text-primary/20 transition-colors pointer-events-none">
                  <MessageSquare className="h-4 w-4" />
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground/80 leading-relaxed px-1">
                <span className="text-primary font-bold">Strategic Intent:</span> This text tells the AI how to prioritize your background. Use it to clarify your next move so the matching engine knows which parts of your experience to weigh most heavily.
              </p>
            </div>
          </div>
        </section>

        {/* Industries Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-5 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <Building className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">Target Industries</h3>
          </div>

          <div className="flex flex-col gap-3 pt-2">
            <div className="flex flex-wrap gap-2">
              {allIndustries.map(industry => {
                const isActive = industries.includes(industry)
                return (
                  <Badge
                    key={industry}
                    variant={isActive ? "default" : "outline"}
                    className={cn(
                      "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                      isActive ? "bg-primary border-primary shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-muted/50"
                    )}
                    onClick={() => toggleItem(industry, industries, setIndustries)}
                  >
                    {industry}
                  </Badge>
                )
              })}
              
              <div className="flex items-center gap-2 px-3 py-1 bg-muted/20 border border-dashed border-border/50 rounded-xl min-w-[140px] focus-within:border-primary/50 transition-colors">
                <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                <input 
                  value={newIndustry}
                  onChange={(e) => setNewIndustry(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddItem(newIndustry, industries, setIndustries, setNewIndustry)}
                  placeholder="Custom industry..."
                  className="bg-transparent border-none outline-none text-xs w-full py-1 placeholder:text-muted-foreground/40"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Excitement Signals Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-5 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <Trophy className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">What excites you in a role?</h3>
          </div>

          <div className="flex flex-col gap-3 pt-2">
            <div className="flex flex-wrap gap-2">
              {allExcitementOptions.map(signal => {
                const isActive = goodMatchSignals.includes(signal)
                return (
                  <Badge
                    key={signal}
                    variant={isActive ? "default" : "outline"}
                    className={cn(
                      "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                      isActive ? "bg-primary border-primary shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-muted/50"
                    )}
                    onClick={() => toggleItem(signal, goodMatchSignals, setGoodMatchSignals)}
                  >
                    {signal}
                  </Badge>
                )
              })}

              <div className="flex items-center gap-2 px-3 py-1 bg-muted/20 border border-dashed border-border/50 rounded-xl min-w-[140px] focus-within:border-primary/50 transition-colors">
                <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                <input 
                  value={newExcitement}
                  onChange={(e) => setNewExcitement(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddItem(newExcitement, goodMatchSignals, setGoodMatchSignals, setNewExcitement)}
                  placeholder="Add custom excitement..."
                  className="bg-transparent border-none outline-none text-xs w-full py-1 placeholder:text-muted-foreground/40"
                />
              </div>
            </div>
          </div>
        </section>

        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-6 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <Building className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">Strategic Company Exceptions</h3>
          </div>

          <div className="flex flex-col gap-3 pt-2">
            <p className="text-xs text-muted-foreground leading-relaxed">
              Keep this blank unless certain company qualities justify a strategic exception. This stays explicit and generic: the scorer only uses signals you choose here and only when companies are tagged with matching signals.
            </p>

            <div className="flex flex-wrap gap-2">
              {COMPANY_QUALITY_SIGNAL_OPTIONS.map((signal) => {
                const isActive = companyQualitySignals.includes(signal.value)
                return (
                  <Badge
                    key={signal.value}
                    variant={isActive ? "default" : "outline"}
                    className={cn(
                      "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                      isActive ? "bg-primary border-primary shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-muted/50"
                    )}
                    onClick={() => toggleCompanySignal(signal.value)}
                  >
                    {signal.label}
                  </Badge>
                )
              })}

              <div className="flex items-center gap-2 px-3 py-1 bg-muted/20 border border-dashed border-border/50 rounded-xl min-w-[180px] focus-within:border-primary/50 transition-colors">
                <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                <input
                  value={newCompanySignal}
                  onChange={(e) => setNewCompanySignal(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddCompanySignal()}
                  placeholder="Add custom signal..."
                  className="bg-transparent border-none outline-none text-xs w-full py-1 placeholder:text-muted-foreground/40"
                />
              </div>
            </div>

            {companyQualitySignals.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {companyQualitySignals.map((signal) => (
                  <Badge
                    key={signal}
                    variant="outline"
                    className="rounded-xl bg-primary/5 border-primary/20 text-primary gap-1.5 px-3 py-1.5"
                  >
                    {getCompanyQualitySignalLabel(signal)}
                    <button
                      type="button"
                      onClick={() => toggleCompanySignal(signal)}
                      className="rounded-full hover:bg-primary/10"
                      aria-label={`Remove ${signal}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}

            <div className={cn(
              "flex items-start justify-between gap-4 rounded-2xl border p-4 transition-colors",
              companyQualitySignals.length > 0 ? "border-primary/20 bg-primary/5" : "border-border/40 bg-muted/10"
            )}>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-foreground">
                  Allow lower-seniority roles only when those signals match
                </p>
                <p className="text-xs text-muted-foreground leading-relaxed max-w-xl">
                  Use this for explicit stretch exceptions, not as a default downgrade of your seniority preferences.
                </p>
              </div>
              <Switch
                checked={allowLowerSeniorityAtStrategicCompanies}
                disabled={companyQualitySignals.length === 0}
                onCheckedChange={(checked) => setAllowLowerSeniorityAtStrategicCompanies(Boolean(checked))}
              />
            </div>
          </div>
        </section>

        {/* Deal-breakers Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-6 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-destructive/10 rounded-xl text-destructive">
              <Ban className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">Deal-breakers</h3>
          </div>

          <div className="flex flex-col gap-3 pt-2">
            <div className="flex flex-wrap gap-2">
              {allDealBreakerOptions.map(breaker => {
                const isActive = dealBreakers.includes(breaker)
                return (
                  <Badge
                    key={breaker}
                    variant={isActive ? "destructive" : "outline"}
                    className={cn(
                      "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto text-left leading-relaxed",
                      isActive ? "bg-destructive border-destructive shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
                    )}
                    onClick={() => toggleItem(breaker, dealBreakers, setDealBreakers)}
                  >
                    {breaker}
                  </Badge>
                )
              })}

              <div className="flex items-center gap-2 px-3 py-1 bg-muted/20 border border-dashed border-border/50 rounded-xl min-w-[140px] focus-within:border-destructive/50 transition-colors">
                <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                <input 
                  value={newDealBreaker}
                  onChange={(e) => setNewDealBreaker(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddItem(newDealBreaker, dealBreakers, setDealBreakers, setNewDealBreaker)}
                  placeholder="Add custom deal-breaker..."
                  className="bg-transparent border-none outline-none text-xs w-full py-1 placeholder:text-muted-foreground/40"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Additional Context Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-6 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <MessageSquare className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">Anything else?</h3>
          </div>

          <div className="flex flex-col gap-3 pt-2">
            <Textarea 
              value={additionalContext}
              onChange={(e) => setAdditionalContext(e.target.value)}
              placeholder="Any other preferences, technologies you want to avoid, or specific company sizes you prefer..."
              className="min-h-[80px] bg-background/50 border-border/50 rounded-2xl p-4 text-sm"
            />
          </div>
        </section>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-border/20">
        <Button 
          onClick={handleNext}
          className="w-full sm:flex-[2] h-14 text-lg font-bold shadow-xl gap-2 rounded-2xl hover:scale-[1.01] transition-all bg-primary hover:bg-primary/90"
        >
          Finalize & Preview
          <ChevronRight className="h-5 w-5" />
        </Button>
        <Button 
          onClick={() => onBack()} 
          variant="outline" 
          className="w-full sm:flex-1 h-14 text-base rounded-2xl border-border/50 hover:bg-muted/30 gap-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Back
        </Button>
      </div>
    </div>
  )
}
