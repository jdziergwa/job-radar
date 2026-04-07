'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { 
  User, 
  Briefcase, 
  Wrench, 
  GraduationCap, 
  Globe, 
  X, 
  Plus, 
  ChevronLeft, 
  Check,
  Building2,
  Calendar,
  ExternalLink,
  Edit2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Save
} from 'lucide-react'
import { cn } from '@/lib/utils'

import { components } from '@/lib/api/types'
import { WizardData } from '../types'

type ExperienceEntry = components["schemas"]["ExperienceEntry"]
type EducationEntry = components["schemas"]["EducationEntry"]
type PortfolioEntry = components["schemas"]["PortfolioEntry"]
type CVAnalysis = components["schemas"]["CVAnalysisResponse"]

interface StepProps {
  onNext: (data?: Partial<WizardData>) => void
  onBack: (data?: Partial<WizardData>) => void
  data: Partial<WizardData>
}

export function ReviewProfile({ onNext, onBack, data }: StepProps) {
  const [profile, setProfile] = useState<CVAnalysis>(data.cvAnalysis as CVAnalysis)
  const [newSkill, setNewSkill] = useState<{ [category: string]: string }>({})
  const [newCategoryName, setNewCategoryName] = useState('')
  const [showAddCategory, setShowAddCategory] = useState(false)
  const [editingExpIdx, setEditingExpIdx] = useState<number | null>(null)
  const [expandedExpIdx, setExpandedExpIdx] = useState<number[] | null>(null)
  const [editingEduIdx, setEditingEduIdx] = useState<number | null>(null)
  const [editingProjIdx, setEditingProjIdx] = useState<number | null>(null)

  const handleRemoveSkill = (category: string, skillToRemove: string) => {
    setProfile(prev => ({
      ...prev,
      skills: {
        ...prev.skills,
        [category]: prev.skills[category].filter(s => s !== skillToRemove)
      }
    }))
  }

  const handleAddSkill = (category: string) => {
    const skillName = newSkill[category]?.trim()
    if (!skillName) return

    setProfile(prev => ({
      ...prev,
      skills: {
        ...prev.skills,
        [category]: [...prev.skills[category], skillName]
      }
    }))
    setNewSkill(prev => ({ ...prev, [category]: '' }))
  }

  const handleAddCategory = () => {
    const category = newCategoryName.trim()
    if (!category || profile.skills[category]) return

    setProfile(prev => ({
      ...prev,
      skills: {
        ...prev.skills,
        [category]: []
      }
    }))
    setNewCategoryName('')
    setShowAddCategory(false)
  }

  const toggleExpandedExp = (idx: number) => {
    setExpandedExpIdx(prev => {
      const current = prev || []
      return current.includes(idx) ? current.filter(i => i !== idx) : [...current, idx]
    })
  }

  const handleRemoveExperience = (idx: number) => {
    setProfile(prev => ({
      ...prev,
      experience: prev.experience.filter((_, i) => i !== idx)
    }))
    if (editingExpIdx === idx) setEditingExpIdx(null)
  }

  const handleAddExperience = () => {
    const newExp: ExperienceEntry = {
      company: 'New Company',
      role: 'New Role',
      dates: '2024 — Present',
      industry: 'Software',
      highlights: []
    }
    setProfile(prev => ({
      ...prev,
      experience: [newExp, ...prev.experience]
    }))
    setEditingExpIdx(0)
    setExpandedExpIdx(prev => [0, ...(prev || [])])
  }

  const handleRemoveEducation = (idx: number) => {
    setProfile(prev => ({
      ...prev,
      education: prev.education.filter((_, i) => i !== idx)
    }))
    if (editingEduIdx === idx) setEditingEduIdx(null)
  }

  const handleAddEducation = () => {
    const newEdu: EducationEntry = {
      school: 'New University',
      degree: 'Degree Name',
      start_year: '2020',
      end_year: '2024'
    }
    setProfile(prev => ({
      ...prev,
      education: [newEdu, ...prev.education]
    }))
    setEditingEduIdx(0)
  }

  const handleRemovePortfolio = (idx: number) => {
    setProfile(prev => ({
      ...prev,
      portfolio: prev.portfolio.filter((_, i) => i !== idx)
    }))
    if (editingProjIdx === idx) setEditingProjIdx(null)
  }

  const handleAddPortfolio = () => {
    const newProj: PortfolioEntry = {
      name: 'New Project',
      url: 'https://github.com/yourname/project',
      description: 'Brief description of your project and impact.',
      technologies: []
    }
    setProfile(prev => ({
      ...prev,
      portfolio: [newProj, ...prev.portfolio]
    }))
    setEditingProjIdx(0)
  }

  return (
    <div className="flex flex-col gap-8 py-4 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto w-full">
      <div className="text-center space-y-1 bg-background/50 py-6 -mt-4 border-b border-border/20 mb-4">
        <h2 className="text-2xl font-bold tracking-tight">Review your profile</h2>
        <p className="text-muted-foreground text-sm max-w-sm mx-auto">We've extracted this from your CV. Make sure everything looks right.</p>
      </div>

      <div className="grid gap-6">
        {/* About You Card */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm">
          <div className="flex items-center gap-3 border-b border-border/20 pb-5 mb-2">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <User className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-lg text-foreground">About You</h3>
          </div>
          
          <div className="grid sm:grid-cols-2 gap-8 pt-2">
            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">Current Role</label>
              <Input 
                value={profile.current_role} 
                onChange={(e) => setProfile(prev => ({ ...prev, current_role: e.target.value }))}
                className="h-12 bg-background/50 border-border/50 focus:border-primary/50 transition-all text-sm rounded-2xl"
                placeholder="e.g. Senior Software Engineer"
              />
            </div>
            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 ml-1 block">Total Experience</label>
              <Input 
                type="number"
                value={profile.experience_years || 0} 
                onChange={(e) => setProfile(prev => ({ ...prev, experience_years: parseInt(e.target.value) || 0 }))}
                className="h-12 bg-background/50 border-border/50 focus:border-primary/50 transition-all text-sm rounded-2xl"
                placeholder="e.g. 5"
              />
            </div>
          </div>
        </section>

        {/* Experience Card */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm">
          <div className="flex items-center justify-between border-b border-border/20 pb-5 mb-2">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-xl text-primary">
                <Briefcase className="h-5 w-5" />
              </div>
              <h3 className="font-bold text-lg text-foreground">Work Experience</h3>
            </div>
            <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleAddExperience}
                className="h-8 px-3 text-xs gap-1.5 rounded-xl hover:bg-primary/10 hover:text-primary transition-colors border border-border/20"
              >
                <Plus className="h-3 w-3" />
                Add Job
            </Button>
          </div>

          <div className="space-y-6 relative before:absolute before:left-[19px] before:top-2 before:bottom-2 before:w-0.5 before:bg-border/30">
            {profile.experience.map((exp, idx) => {
              const isEditing = editingExpIdx === idx
              const isExpanded = (expandedExpIdx || []).includes(idx)

              return (
                <div key={idx} className="relative pl-12 group">
                  <div className="absolute left-0 top-1.5 h-10 w-10 bg-background border border-border/50 rounded-xl flex items-center justify-center group-hover:border-primary/30 transition-colors z-10 shadow-sm">
                    <Building2 className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>
                  
                  {isEditing ? (
                    <div className="bg-muted/10 p-5 rounded-2xl border border-primary/20 space-y-4 animate-in zoom-in-95 duration-200">
                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold uppercase tracking-tight text-muted-foreground/70 ml-1">Company</label>
                          <Input 
                            value={exp.company} 
                            onChange={(e) => {
                              const newExp = [...profile.experience]
                              newExp[idx].company = e.target.value
                              setProfile({ ...profile, experience: newExp })
                            }}
                            className="h-9 text-sm bg-background"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold uppercase tracking-tight text-muted-foreground/70 ml-1">Industry</label>
                          <Input 
                            value={exp.industry || ''} 
                            onChange={(e) => {
                              const newExp = [...profile.experience]
                              newExp[idx].industry = e.target.value
                              setProfile({ ...profile, experience: newExp })
                            }}
                            className="h-9 text-sm bg-background"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold uppercase tracking-tight text-muted-foreground/70 ml-1">Role</label>
                          <Input 
                            value={exp.role} 
                            onChange={(e) => {
                              const newExp = [...profile.experience]
                              newExp[idx].role = e.target.value
                              setProfile({ ...profile, experience: newExp })
                            }}
                            className="h-9 text-sm bg-background"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold uppercase tracking-tight text-muted-foreground/70 ml-1">Dates</label>
                          <Input 
                            value={exp.dates} 
                            onChange={(e) => {
                              const newExp = [...profile.experience]
                              newExp[idx].dates = e.target.value
                              setProfile({ ...profile, experience: newExp })
                            }}
                            className="h-9 text-sm bg-background"
                          />
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold uppercase tracking-tight text-muted-foreground/70 ml-1">Highlights (One per line)</label>
                        <textarea 
                          value={(exp.highlights || []).join('\n')} 
                          onChange={(e) => {
                            const newExp = [...profile.experience]
                            newExp[idx].highlights = e.target.value.split('\n')
                            setProfile({ ...profile, experience: newExp })
                          }}
                          className="w-full min-h-[100px] p-3 text-xs bg-background border border-border/50 rounded-xl focus:outline-none focus:ring-1 focus:ring-primary/20 resize-none font-sans"
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditingExpIdx(null)} className="h-8 text-xs underline">Cancel</Button>
                        <Button size="sm" onClick={() => setEditingExpIdx(null)} className="h-8 text-xs gap-1.5 px-4"><Save className="size-3"/> Save</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-base">{exp.company}</span>
                          {exp.industry && (
                            <Badge variant="outline" className="text-[10px] uppercase tracking-tighter opacity-70">
                              {exp.industry}
                            </Badge>
                          )}
                        </div>
                        <div className="flex opacity-0 group-hover:opacity-100 transition-opacity gap-1">
                           <Button variant="ghost" size="icon" onClick={() => setEditingExpIdx(idx)} className="size-7 hover:bg-primary/10 hover:text-primary"><Edit2 className="size-3.5"/></Button>
                           <Button variant="ghost" size="icon" onClick={() => handleRemoveExperience(idx)} className="size-7 hover:bg-destructive/10 hover:text-destructive"><Trash2 className="size-3.5"/></Button>
                        </div>
                      </div>
                      <div className="text-sm font-medium text-foreground/80">{exp.role}</div>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <Calendar className="h-3 w-3" />
                          {exp.dates}
                        </div>
                        {exp.highlights && exp.highlights.length > 0 && (
                          <button 
                            onClick={() => toggleExpandedExp(idx)}
                            className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-primary/70 hover:text-primary transition-colors"
                          >
                            {isExpanded ? <ChevronUp className="size-3"/> : <ChevronDown className="size-3"/>}
                            {isExpanded ? 'Hide Details' : 'Show Details'}
                          </button>
                        )}
                      </div>

                      {isExpanded && exp.highlights && (
                        <ul className="mt-3 space-y-1.5 animate-in slide-in-from-top-2 duration-300">
                          {exp.highlights.map((h, hIdx) => h.trim() && (
                            <li key={hIdx} className="flex gap-2 text-xs text-muted-foreground leading-relaxed">
                              <span className="text-primary mt-1">•</span>
                              {h}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <p className="text-[10px] text-muted-foreground/50 uppercase tracking-widest font-bold text-center pt-2">Full job descriptions are used by the AI but not shown here</p>
        </section>

        {/* Technical Skills Card */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm font-sans">
          <div className="flex items-center justify-between border-b border-border/20 pb-5 mb-2">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-xl text-primary">
                <Wrench className="h-5 w-5" />
              </div>
              <h3 className="font-bold text-lg text-foreground">Technical Skills</h3>
            </div>
            {!showAddCategory && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setShowAddCategory(true)}
                className="h-8 px-3 text-xs gap-1.5 rounded-xl hover:bg-primary/10 hover:text-primary transition-colors border border-border/20"
              >
                <Plus className="h-3 w-3" />
                Add Category
              </Button>
            )}
          </div>

          {showAddCategory && (
            <div className="p-4 bg-primary/5 border border-primary/20 rounded-2xl flex gap-3 animate-in zoom-in-95 duration-300">
               <Input 
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddCategory()}
                placeholder="Category name (e.g. DevOps, Cloud...)"
                autoFocus
                className="h-10 bg-background/50"
               />
               <Button size="sm" onClick={handleAddCategory} className="h-10 px-4 rounded-xl">Add</Button>
               <Button size="icon" variant="ghost" onClick={() => setShowAddCategory(false)} className="h-10 w-10 rounded-xl"><X className="h-4 w-4"/></Button>
            </div>
          )}

          <div className="grid gap-8">
            {Object.entries(profile.skills).map(([category, skills]) => (
              <div key={category} className="flex flex-col gap-3">
                <h4 className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70 pl-1">{category}</h4>
                <div className="flex flex-wrap gap-2">
                  {skills.map((skill, sIdx) => (
                    <Badge 
                      key={sIdx} 
                      variant="secondary"
                      className="px-3 py-1.5 text-sm font-medium bg-background border-border/40 hover:border-destructive/30 hover:bg-destructive/5 transition-all group/skill cursor-default gap-2 rounded-xl"
                    >
                      {skill}
                      <button 
                        onClick={() => handleRemoveSkill(category, skill)}
                        className="opacity-0 group-hover/skill:opacity-100 p-0.5 hover:bg-destructive/20 rounded-full transition-all text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                  <div className="relative group">
                    <Input 
                      value={newSkill[category] || ''}
                      onChange={(e) => setNewSkill(prev => ({ ...prev, [category]: e.target.value }))}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddSkill(category)}
                      placeholder="Add skill..."
                      className="h-8 w-32 px-3 py-1.5 text-xs bg-muted/20 border-dotted border-border/40 focus:w-48 transition-all rounded-xl"
                    />
                    <Plus className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground/50 pointer-events-none group-focus-within:text-primary transition-colors" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Education Card */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm">
          <div className="flex items-center justify-between border-b border-border/20 pb-5 mb-2">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-xl text-primary">
                <GraduationCap className="h-5 w-5" />
              </div>
              <h3 className="font-bold text-lg text-foreground">Education</h3>
            </div>
            <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleAddEducation}
                className="h-8 px-3 text-xs gap-1.5 rounded-xl hover:bg-primary/10 hover:text-primary transition-colors border border-border/20"
              >
                <Plus className="h-3 w-3" />
                Add School
            </Button>
          </div>
          <div className="space-y-4">
            {profile.education?.map((edu, idx) => {
              const isEditing = editingEduIdx === idx
              
              return (
                <div key={idx} className="flex gap-4 group relative">
                  <div className="h-10 w-10 bg-muted/30 rounded-xl flex items-center justify-center shrink-0">
                    <Globe className="h-4 w-4 text-muted-foreground" />
                  </div>
                  
                  {isEditing ? (
                    <div className="flex-1 bg-muted/10 p-4 rounded-2xl border border-primary/20 space-y-3 animate-in zoom-in-95 duration-200">
                       <Input 
                        value={edu.school} 
                        onChange={(e) => {
                          const newEdu = [...profile.education]
                          newEdu[idx].school = e.target.value
                          setProfile({ ...profile, education: newEdu })
                        }}
                        placeholder="University Name"
                        className="h-8 text-sm bg-background"
                      />
                       <Input 
                        value={edu.degree} 
                        onChange={(e) => {
                          const newEdu = [...profile.education]
                          newEdu[idx].degree = e.target.value
                          setProfile({ ...profile, education: newEdu })
                        }}
                        placeholder="Degree / Major"
                        className="h-8 text-sm bg-background"
                      />
                       <Input 
                        value={edu.start_year || ''} 
                        onChange={(e) => {
                          const newEdu = [...profile.education]
                          newEdu[idx].start_year = e.target.value
                          setProfile({ ...profile, education: newEdu })
                        }}
                        placeholder="Start Year"
                        className="h-8 text-sm bg-background"
                      />
                       <Input 
                        value={edu.end_year || ''} 
                        onChange={(e) => {
                          const newEdu = [...profile.education]
                          newEdu[idx].end_year = e.target.value
                          setProfile({ ...profile, education: newEdu })
                        }}
                        placeholder="End Year (or Present)"
                        className="h-8 text-sm bg-background"
                      />
                       <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditingEduIdx(null)} className="h-7 text-[10px] underline">Cancel</Button>
                        <Button size="sm" onClick={() => setEditingEduIdx(null)} className="h-7 text-[10px] gap-1 px-3">Save</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex justify-between items-start">
                      <div>
                        <div className="font-bold">{edu.school}</div>
                        <div className="text-sm opacity-80">{edu.degree}</div>
                        <div className="text-xs text-muted-foreground">{edu.start_year && edu.end_year ? `${edu.start_year} — ${edu.end_year}` : (edu.start_year || edu.end_year || '')}</div>
                      </div>
                      <div className="flex opacity-0 group-hover:opacity-100 transition-opacity gap-1">
                        <Button variant="ghost" size="icon" onClick={() => setEditingEduIdx(idx)} className="size-7 hover:bg-primary/10 hover:text-primary"><Edit2 className="size-3.5"/></Button>
                        <Button variant="ghost" size="icon" onClick={() => handleRemoveEducation(idx)} className="size-7 hover:bg-destructive/10 hover:text-destructive"><Trash2 className="size-3.5"/></Button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
            {(!profile.education || profile.education.length === 0) && (
              <p className="text-xs text-muted-foreground text-center py-4">No education details added.</p>
            )}
          </div>
        </section>

        {/* Portfolio Card */}
        <section className="bg-background/40 backdrop-blur-sm border border-border/50 rounded-3xl p-6 flex flex-col gap-8 shadow-sm">
          <div className="flex items-center justify-between border-b border-border/20 pb-5 mb-2">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-xl text-primary">
                <Globe className="h-5 w-5" />
              </div>
              <h3 className="font-bold text-lg text-foreground">Portfolio & Projects</h3>
            </div>
            <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleAddPortfolio}
                className="h-8 px-3 text-xs gap-1.5 rounded-xl hover:bg-primary/10 hover:text-primary transition-colors border border-border/20"
              >
                <Plus className="h-3 w-3" />
                Add Project
            </Button>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {profile.portfolio?.map((project, idx) => {
              const isEditing = editingProjIdx === idx

              return (
                <div key={idx} className="group relative p-4 bg-muted/20 border border-border/30 rounded-2xl flex flex-col justify-between min-h-[140px]">
                  {isEditing ? (
                    <div className="space-y-3 animate-in zoom-in-95 duration-200">
                       <Input 
                        value={project.name} 
                        onChange={(e) => {
                          const newProj = [...profile.portfolio]
                          newProj[idx].name = e.target.value
                          setProfile({ ...profile, portfolio: newProj })
                        }}
                        placeholder="Project Name"
                        className="h-8 text-sm bg-background"
                      />
                       <Input 
                        value={project.url} 
                        onChange={(e) => {
                          const newProj = [...profile.portfolio]
                          newProj[idx].url = e.target.value
                          setProfile({ ...profile, portfolio: newProj })
                        }}
                        placeholder="Project URL (GitHub, Website...)"
                        className="h-8 text-sm bg-background"
                      />
                      <textarea 
                        value={project.description || ''} 
                        onChange={(e) => {
                          const newProj = [...profile.portfolio]
                          newProj[idx].description = e.target.value
                          setProfile({ ...profile, portfolio: newProj })
                        }}
                        placeholder="Impact and technologies used..."
                        className="w-full min-h-[60px] p-2 text-xs bg-background border border-border/50 rounded-xl focus:outline-none focus:ring-1 focus:ring-primary/20 resize-none font-sans"
                      />
                       <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditingProjIdx(null)} className="h-7 text-[10px] underline">Cancel</Button>
                        <Button size="sm" onClick={() => setEditingProjIdx(null)} className="h-7 text-[10px] gap-1 px-3">Save</Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span className="font-bold">{project.name}</span>
                          <div className="flex items-center gap-1">
                            <div className="flex opacity-0 group-hover:opacity-100 transition-opacity">
                              <Button variant="ghost" size="icon" onClick={() => setEditingProjIdx(idx)} className="size-7 hover:bg-primary/10 hover:text-primary"><Edit2 className="size-3.5"/></Button>
                              <Button variant="ghost" size="icon" onClick={() => handleRemovePortfolio(idx)} className="size-7 hover:bg-destructive/10 hover:text-destructive"><Trash2 className="size-3.5"/></Button>
                            </div>
                            <a 
                              href={project.url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="p-1.5 hover:bg-primary/10 rounded-lg text-primary transition-colors ml-1"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">{project.description}</p>
                      </div>
                      {project.technologies && project.technologies.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-3">
                          {project.technologies.map(t => (
                            <Badge key={t} variant="ghost" className="text-[9px] h-4 px-1.5 bg-background/50">
                              {t}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )
            })}
            {(!profile.portfolio || profile.portfolio.length === 0) && (
              <p className="text-xs text-muted-foreground text-center py-8 col-span-2">No portfolio projects added.</p>
            )}
          </div>
        </section>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-border/20">
        <Button 
          onClick={() => onNext({ cvAnalysis: profile })} 
          className="w-full sm:flex-[2] h-14 text-lg font-bold shadow-xl gap-2 rounded-2xl hover:scale-[1.01] transition-all bg-primary hover:bg-primary/90"
        >
          <Check className="h-5 w-5" />
          Looks good, continue
        </Button>
        <Button 
          onClick={() => onBack()} 
          variant="outline" 
          className="w-full sm:flex-1 h-14 text-base rounded-2xl border-border/50 hover:bg-muted/30 gap-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Re-upload CV
        </Button>
      </div>
    </div>
  )
}

