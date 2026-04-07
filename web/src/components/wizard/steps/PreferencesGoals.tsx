'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
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

import { WizardData } from '../types'

interface StepProps {
  onNext: (data?: Partial<WizardData>) => void
  onBack: () => void
  data: Partial<WizardData>
}

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

export function PreferencesGoals({ onNext, onBack, data }: StepProps) {
  const analysis = data.cvAnalysis
  
  const [careerDirection, setCareerDirection] = useState(analysis?.suggested_career_direction || '')
  const [industries, setIndustries] = useState<string[]>([])
  const [goodMatchSignals, setGoodMatchSignals] = useState<string[]>([])
  const [dealBreakers, setDealBreakers] = useState<string[]>([])
  const [additionalContext, setAdditionalContext] = useState('')
  
  const [newIndustry, setNewIndustry] = useState('')
  const [newExcitement, setNewExcitement] = useState('')
  const [newDealBreaker, setNewDealBreaker] = useState('')

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

  const handleNext = () => {
    onNext({
      careerDirection,
      industries,
      goodMatchSignals,
      dealBreakers,
      additionalContext
    })
  }

  return (
    <div className="flex flex-col gap-8 py-4 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto w-full">
      <div className="text-center space-y-1 bg-background/50 py-6 -mt-4 border-b border-border/20 mb-4">
        <h2 className="text-2xl font-bold tracking-tight">Preferences & Goals</h2>
        <p className="text-muted-foreground text-sm max-w-sm mx-auto">Tell us about your career aspirations and boundaries.</p>
      </div>

      <div className="grid gap-5">
        {/* Career Direction Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-5 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <Compass className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">Career Direction</h3>
          </div>

          <div className="flex flex-col gap-3 pt-2">
            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">
                Where do you see your career going?
              </label>
              <Textarea 
                value={careerDirection}
                onChange={(e) => setCareerDirection(e.target.value)}
                placeholder="e.g. I want to transition into Lead Software Engineering roles focalized on architecture and tech ownership..."
                className="min-h-[120px] bg-background/50 border-border/50 rounded-2xl p-4 text-sm leading-relaxed"
              />
              <p className="text-[10px] text-muted-foreground/60 italic ml-1">
                This helper text was generated based on your CV profile. Edit it to better reflect your goals.
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
              {INDUSTRIES.map(industry => {
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
              {EXCITEMENT_SIGNALS.map(signal => {
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
                  placeholder="Add signal..."
                  className="bg-transparent border-none outline-none text-xs w-full py-1 placeholder:text-muted-foreground/40"
                />
              </div>
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
              {DEAL_BREAKERS.map(item => {
                const isActive = dealBreakers.includes(item)
                return (
                  <Badge
                    key={item}
                    variant={isActive ? "destructive" : "outline"}
                    className={cn(
                      "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                      isActive ? "bg-destructive border-destructive shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
                    )}
                    onClick={() => toggleItem(item, dealBreakers, setDealBreakers)}
                  >
                    {item}
                  </Badge>
                )
              })}

              <div className="flex items-center gap-2 px-3 py-1 bg-muted/20 border border-dashed border-border/50 rounded-xl min-w-[140px] focus-within:border-destructive/50 transition-colors">
                <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                <input 
                  value={newDealBreaker}
                  onChange={(e) => setNewDealBreaker(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddItem(newDealBreaker, dealBreakers, setDealBreakers, setNewDealBreaker)}
                  placeholder="Add deal-breaker..."
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
