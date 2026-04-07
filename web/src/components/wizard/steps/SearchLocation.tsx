'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from '@/components/ui/select'
import { 
  Search, 
  MapPin, 
  Globe2, 
  X, 
  Plus,
  ChevronLeft,
  ChevronRight,
  Wifi,
  Building2,
  Home
} from 'lucide-react'
import { cn } from '@/lib/utils'

import { useEffect } from 'react'
import { StepProps } from '../types'

const SENIORITY_LEVELS = ['Junior', 'Mid', 'Senior', 'Lead', 'Staff', 'Principal']
const WORK_AUTH = ['EU citizen', 'US citizen', 'UK right to work', 'Need visa sponsorship', 'Other']
const REMOTE_PREF = [
  { id: 'remote', label: 'Fully Remote', icon: Wifi },
  { id: 'hybrid', label: 'Hybrid OK', icon: Building2 },
  { id: 'onsite', label: 'On-site OK', icon: Home },
]
const REGIONS = [
  'Europe', 'UK', 'US/North America', 'Global/Worldwide', 
  'Germany', 'Netherlands', 'Switzerland', 'Spain', 
  'Portugal', 'France', 'Nordics', 'Middle East', 'Asia-Pacific'
]
const TIMEZONE_PREFS = [
  { id: 'overlap_strict', label: 'Same/Overlap (±2h)' },
  { id: 'americas', label: 'Americas (UTC-3 to UTC-8)' },
  { id: 'emea', label: 'EMEA (UTC-1 to UTC+4)' },
  { id: 'apac', label: 'APAC (UTC+7 to UTC+12)' },
  { id: 'any', label: 'Any Timezone' }
]

export function SearchLocation({ onNext, onBack, onUpdate, data }: StepProps) {
  const analysis = data.cvAnalysis
  
  const [targetRoles, setTargetRoles] = useState<string[]>(data.targetRoles || analysis?.suggested_target_roles || [])
  const [newRole, setNewRole] = useState('')
  const [seniority, setSeniority] = useState<string[]>(
    data.seniority || (analysis?.inferred_seniority ? [analysis.inferred_seniority.toLowerCase()] : ['senior'])
  )
  const [location, setLocation] = useState(data.location || '')
  const [workAuth, setWorkAuth] = useState<string>(data.workAuth || '')
  const [remotePref, setRemotePref] = useState<string[]>(data.remotePref || ['remote'])
  const [primaryRemotePref, setPrimaryRemotePref] = useState<string>(data.primaryRemotePref || 'remote')
  const [timezonePref, setTimezonePref] = useState<string>(data.timezonePref || 'local')
  const [targetRegions, setTargetRegions] = useState<string[]>(data.targetRegions || ['Europe'])
  const [excludedRegions, setExcludedRegions] = useState<string[]>(data.excludedRegions || [])

  // Auto-sync state back to wizardData for refresh resilience
  useEffect(() => {
    onUpdate({
      targetRoles,
      seniority,
      location,
      workAuth,
      remotePref,
      primaryRemotePref,
      timezonePref,
      targetRegions,
      excludedRegions
    })
  }, [targetRoles, seniority, location, workAuth, remotePref, primaryRemotePref, timezonePref, targetRegions, excludedRegions, onUpdate])

  const handleAddRole = () => {
    const role = newRole.trim()
    if (role && !targetRoles.includes(role)) {
      setTargetRoles([...targetRoles, role])
      setNewRole('')
    }
  }

  const toggleRegion = (region: string, isExcluded: boolean = false) => {
    if (isExcluded) {
      setExcludedRegions(prev => 
        prev.includes(region) ? prev.filter(r => r !== region) : [...prev, region]
      )
      // Remove from target if added to excluded
      setTargetRegions(prev => prev.filter(r => r !== region))
    } else {
      setTargetRegions(prev => 
        prev.includes(region) ? prev.filter(r => r !== region) : [...prev, region]
      )
      // Remove from excluded if added to target
      setExcludedRegions(prev => prev.filter(r => r !== region))
    }
  }

  const isValid = targetRoles.length > 0 && location.trim().length > 0 && remotePref.length > 0

  const handleNext = () => {
    if (!isValid) return
    onNext({
      targetRoles,
      seniority,
      location,
      workAuth,
      remotePref,
      primaryRemotePref,
      timezonePref,
      targetRegions,
      excludedRegions
    })
  }

  return (
    <div className="flex flex-col gap-8 py-4 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto w-full">
      <div className="text-center space-y-1 bg-background/50 py-6 -mt-4 border-b border-border/20 mb-4">
        <h2 className="text-2xl font-bold tracking-tight">Search & Location</h2>
        <p className="text-muted-foreground text-sm max-w-sm mx-auto">Where and what jobs are you looking for?</p>
      </div>

      <div className="grid gap-6">
        {/* Roles Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <Search className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">What roles are you looking for?</h3>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">Target Job Titles *</label>
              <div className="flex flex-wrap gap-2 p-3 bg-muted/20 border border-border/30 rounded-2xl min-h-[56px]">
                {targetRoles.map((role, idx) => (
                  <Badge 
                    key={idx} 
                    className="pl-3 pr-1 py-1.5 text-sm font-medium bg-primary/10 text-primary border-primary/20 hover:bg-primary/20 transition-all gap-1 rounded-xl group"
                  >
                    {role}
                    <button 
                      onClick={() => setTargetRoles(targetRoles.filter(r => r !== role))}
                      className="p-0.5 hover:bg-primary/20 rounded-full transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                <div className="relative flex-1 min-w-[120px]">
                  <input 
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        handleAddRole()
                      }
                    }}
                    placeholder={targetRoles.length === 0 ? "e.g. Senior Software Engineer" : "Add another..."}
                    className="w-full bg-transparent border-none outline-none text-sm h-7 placeholder:text-muted-foreground/50 focus:ring-0"
                  />
                  {newRole && (
                    <button 
                      onClick={handleAddRole}
                      className="absolute right-0 top-1/2 -translate-y-1/2 p-1 bg-primary text-primary-foreground rounded-lg"
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">Expected Seniority</label>
              <div className="flex flex-wrap gap-2">
                {SENIORITY_LEVELS.map(level => {
                  const val = level.toLowerCase()
                  const isSelected = seniority.includes(val)
                  return (
                    <Badge
                      key={level}
                      variant={isSelected ? "default" : "outline"}
                      className={cn(
                        "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                        isSelected 
                          ? "bg-primary border-primary shadow-lg scale-105" 
                          : "bg-background/30 border-border/50 hover:bg-muted/50"
                      )}
                      onClick={() => setSeniority(prev => 
                        prev.includes(val) ? prev.filter(s => s !== val) : [...prev, val]
                      )}
                    >
                      {level}
                    </Badge>
                  )
                })}
              </div>
            </div>
          </div>
        </section>

        {/* Location Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <MapPin className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">Where do you want to work?</h3>
          </div>

          <div className="grid sm:grid-cols-2 gap-8 pt-2">
            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">Where are you based? *</label>
              <div className="relative">
                <Input 
                  value={location} 
                  onChange={(e) => setLocation(e.target.value)}
                  className="h-12 pl-12 bg-background/50 border-border/50 text-sm rounded-2xl"
                  placeholder="e.g. Berlin, Germany"
                />
                <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">Work Authorization</label>
              <div className="relative w-full">
                <Globe2 className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground z-10" />
                <Select value={workAuth} onValueChange={(val) => val && setWorkAuth(val)}>
                  <SelectTrigger className="w-full !h-12 pl-12 bg-background/50 border-border/50 text-sm !rounded-2xl">
                    <SelectValue placeholder="Select status">
                      {workAuth ? (WORK_AUTH.find(a => a.toLowerCase().replace(/ /g, '_') === workAuth) || workAuth) : null}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {WORK_AUTH.map(auth => (
                      <SelectItem key={auth} value={auth.toLowerCase().replace(/ /g, '_')}>{auth}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Globe2 className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none z-10" />
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-10 pt-4">
            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-2 block">Acceptable Work Setups</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {REMOTE_PREF.map((pref) => {
                  const Icon = pref.icon
                  const isActive = remotePref.includes(pref.id)
                  const city = location.split(',')[0].trim() || 'my location'
                  const label = pref.id === 'remote' ? pref.label : `${pref.label.split(' ')[0]} from ${city}`

                  return (
                    <button
                      key={pref.id}
                      type="button"
                      onClick={() => {
                        setRemotePref(prev => {
                          const next = prev.includes(pref.id) 
                            ? prev.filter(p => p !== pref.id) 
                            : [...prev, pref.id]
                          
                          // Auto-adjust primary if current primary is removed or if it's the first selection
                          if (next.length > 0 && (!next.includes(primaryRemotePref) || prev.length === 0)) {
                            setPrimaryRemotePref(next[0])
                          }
                          return next
                        })
                      }}
                      className={cn(
                        "flex items-center gap-3 p-4 rounded-2xl border transition-all text-left group/card",
                        isActive 
                          ? "bg-primary/10 border-primary text-primary shadow-sm" 
                          : "bg-background/20 border-border/50 text-muted-foreground hover:bg-muted/30"
                      )}
                    >
                      <div className={cn(
                        "p-2 rounded-xl transition-colors",
                        isActive ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground group-hover/card:bg-primary/10 group-hover/card:text-primary"
                      )}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <span className="font-bold text-xs leading-tight">{label}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {remotePref.length > 1 && (
              <div className="flex flex-col gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
                <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-2 block">Primary Preference</label>
                <div className="flex flex-wrap gap-2">
                  {remotePref.map(id => {
                    const pref = REMOTE_PREF.find(p => p.id === id)
                    const isActive = primaryRemotePref === id
                    return (
                      <Badge
                        key={id}
                        variant={isActive ? "default" : "outline"}
                        className={cn(
                          "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                          isActive ? "bg-primary border-primary shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-muted/50"
                        )}
                        onClick={() => setPrimaryRemotePref(id)}
                      >
                        Prefer {id === 'remote' ? 'Remote' : (pref?.label.split(' ')[0] || 'Work')}
                      </Badge>
                    )
                  })}
                </div>
              </div>
            )}

            {remotePref.includes('remote') && (
              <div className="flex flex-col gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
                <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-2 block">Timezone Overlap Preference</label>
                <div className="flex flex-wrap gap-2">
                  {TIMEZONE_PREFS.map(pref => {
                    const isActive = timezonePref === pref.id
                    return (
                      <Badge
                        key={pref.id}
                        variant={isActive ? "default" : "outline"}
                        className={cn(
                          "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                          isActive ? "bg-primary border-primary shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-muted/50"
                        )}
                        onClick={() => setTimezonePref(pref.id)}
                      >
                        {pref.label}
                      </Badge>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Regions Section */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-3">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <Globe2 className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">Target Regions</h3>
          </div>

          <div className="flex flex-col gap-10 pt-4">
            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-2 block">I want to work in...</label>
              <div className="flex flex-wrap gap-2">
                {REGIONS.map(region => {
                  const isSelected = targetRegions.includes(region)
                  return (
                    <Badge
                      key={region}
                      variant={isSelected ? "default" : "outline"}
                      className={cn(
                        "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                        isSelected ? "bg-primary border-primary shadow-lg scale-105" : "bg-background/30 border-border/50 hover:bg-muted/50"
                      )}
                      onClick={() => toggleRegion(region)}
                    >
                      {region}
                    </Badge>
                  )
                })}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-2 block text-destructive/80">Exclude these regions</label>
              <div className="flex flex-wrap gap-2">
                {REGIONS.map(region => {
                  const isExcluded = excludedRegions.includes(region)
                  return (
                    <Badge
                      key={region}
                      variant="outline"
                      className={cn(
                        "cursor-pointer px-4 py-2 text-sm rounded-xl transition-all h-auto",
                        isExcluded 
                          ? "bg-destructive/10 text-destructive border-destructive/50 shadow-sm scale-105" 
                          : "bg-background/20 border-border/30 text-muted-foreground/60 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
                      )}
                      onClick={() => toggleRegion(region, true)}
                    >
                      {region}
                    </Badge>
                  )
                })}
              </div>
            </div>
          </div>
        </section>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-border/20">
        <Button 
          onClick={handleNext}
          disabled={!isValid}
          className="w-full sm:flex-[2] h-14 text-lg font-bold shadow-xl gap-2 rounded-2xl hover:scale-[1.01] transition-all bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:grayscale"
        >
          {isValid ? (
            <>
              Next: Preferences
              <ChevronRight className="h-5 w-5" />
            </>
          ) : (
            "Select at least one role & location"
          )}
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
