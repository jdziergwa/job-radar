'use client'

import React, { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/types'
import { toast } from 'sonner'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger
} from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Plus,
  Trash2,
  Building2,
  Loader2,
  Search,
  Globe,
  AlertCircle,
  PencilLine,
  Sparkles
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import {
  COMPANY_QUALITY_SIGNAL_OPTIONS,
  dedupeCompanyQualitySignals,
  getCompanyQualitySignalLabel,
  normalizeCompanyQualitySignal,
} from '@/lib/company-quality'

const PLATFORMS = [
  { id: 'greenhouse', name: 'Greenhouse' },
  { id: 'lever', name: 'Lever' },
  { id: 'ashby', name: 'Ashby' },
  { id: 'workable', name: 'Workable' },
  { id: 'bamboohr', name: 'BambooHR' },
  { id: 'smartrecruiters', name: 'SmartRecruiters' }
] as const

type PlatformId = typeof PLATFORMS[number]['id']
type TrackedCompany = components["schemas"]["TrackedCompanyEntry"]
type CompaniesByPlatform = components["schemas"]["CompaniesResponse"]
type CompanyEntry = components["schemas"]["CompanyEntry"]
type CompanyUpdateRequest = components["schemas"]["CompanyUpdateRequest"]

interface CompanyFormState {
  name: string
  slug: string
  platform: PlatformId
  companyQualitySignals: string[]
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CompaniesByPlatform | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [isAdding, setIsAdding] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)
  const [newCompanySignal, setNewCompanySignal] = useState('')
  const [editingCompanySignal, setEditingCompanySignal] = useState('')
  const [newCompany, setNewCompany] = useState<CompanyFormState>({
    name: '',
    slug: '',
    platform: 'greenhouse',
    companyQualitySignals: [],
  })
  const [editingCompany, setEditingCompany] = useState<CompanyFormState | null>(null)

  const fetchCompanies = async () => {
    setLoading(true)
    setError(null)
    try {
      const { data, error: apiError } = await api.GET('/api/companies/{profile}', {
        params: {
           path: { profile: 'default' }
        }
      })
      if (apiError) throw new Error('Failed to fetch companies')
      setCompanies(data || null)
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCompanies()
  }, [])

  const toggleSignals = (
    currentSignals: string[],
    nextSignal: string,
    onChange: (signals: string[]) => void
  ) => {
    const normalized = normalizeCompanyQualitySignal(nextSignal)
    if (!normalized) return

    if (currentSignals.includes(normalized)) {
      onChange(currentSignals.filter((signal) => signal !== normalized))
      return
    }

    onChange(dedupeCompanyQualitySignals([...currentSignals, normalized]))
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsAdding(true)
    try {
      const body: CompanyEntry = {
        platform: newCompany.platform,
        slug: newCompany.slug,
        name: newCompany.name,
        company_quality_signals: dedupeCompanyQualitySignals(newCompany.companyQualitySignals),
      }
      const { error: apiError } = await api.POST('/api/companies/{profile}', {
        params: {
          path: { profile: 'default' }
        },
        body,
      })
      if (apiError) throw new Error(typeof apiError === 'string' ? apiError : 'Failed to add company')

      setNewCompany({ ...newCompany, name: '', slug: '', companyQualitySignals: [] })
      setNewCompanySignal('')
      await fetchCompanies()
      toast.success('Company board added')
    } catch (err: any) {
      toast.error(err.message || 'Error adding company')
    } finally {
      setIsAdding(false)
    }
  }

  const handleUpdateCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingCompany) return

    setIsUpdating(true)
    try {
      const body: CompanyUpdateRequest = {
        name: editingCompany.name,
        company_quality_signals: dedupeCompanyQualitySignals(editingCompany.companyQualitySignals),
      }
      const { error: apiError } = await api.PATCH('/api/companies/{profile}/{platform}/{slug}', {
        params: {
          path: {
            profile: 'default',
            platform: editingCompany.platform,
            slug: editingCompany.slug,
          }
        },
        body,
      })

      if (apiError) throw new Error(typeof apiError === 'string' ? apiError : 'Failed to update company')

      setEditingCompany(null)
      setEditingCompanySignal('')
      await fetchCompanies()
      toast.success('Company settings updated')
    } catch (err: any) {
      toast.error(err.message || 'Error updating company')
    } finally {
      setIsUpdating(false)
    }
  }

  const handleDelete = async (platform: string, slug: string) => {
    if (!confirm(`Are you sure you want to remove ${slug}?`)) return

    try {
      const { error: apiError } = await api.DELETE('/api/companies/{profile}/{platform}/{slug}', {
        params: {
          path: { profile: 'default', platform, slug }
        }
      })
      if (apiError) throw new Error('Failed to delete company')
      await fetchCompanies()
      toast.success('Company removed')
    } catch (err: any) {
      toast.error(err.message || 'Error deleting company')
    }
  }

  const filteredCompanies = (platform: PlatformId) => {
    if (!companies || !companies[platform]) return []
    return companies[platform].filter((c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.slug.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }

  const totalCompanies = companies
    ? PLATFORMS.reduce((sum, p) => sum + (companies[p.id]?.length || 0), 0)
    : 0

  return (
    <div className="flex flex-col bg-background/30 px-6 py-8 animate-in fade-in duration-700">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Globe className="h-5 w-5 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 font-mono">Scraper Config</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Tracked Companies</h1>
          <p className="text-muted-foreground mt-1 text-sm max-w-2xl">
            Manage the board slugs for the ATS platforms you want to monitor.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {!loading && companies && (
            <div className="flex items-center gap-2 bg-muted/30 px-3 py-1.5 rounded-full border border-border/50 text-sm font-medium">
              <span className="text-primary font-bold">{totalCompanies}</span>
              <span className="text-muted-foreground">Companies Tracked</span>
            </div>
          )}

          <Dialog>
            <DialogTrigger render={
              <Button className="gap-2 bg-primary/90 hover:bg-primary shadow-lg border-primary/20 transition-all duration-300">
                <Plus className="h-4 w-4" />
                Add Company Board
              </Button>
            } />
            <DialogContent className="border-border/50 bg-background/95 backdrop-blur-xl">
              <form onSubmit={handleAdd}>
                <DialogHeader>
                  <DialogTitle>Add New Company Board</DialogTitle>
                  <DialogDescription>
                    Enter the board details from the ATS URL (e.g., jobs.lever.co/SLUG).
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-6">
                  <div className="grid gap-2">
                    <Label htmlFor="platform">ATS Platform</Label>
                    <select
                      id="platform"
                      value={newCompany.platform}
                      onChange={(e) => setNewCompany({ ...newCompany, platform: e.target.value as PlatformId })}
                      className="flex h-10 w-full rounded-md border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {PLATFORMS.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="name">Display Name</Label>
                    <Input
                      id="name"
                      placeholder="e.g. OpenAI"
                      value={newCompany.name}
                      onChange={(e) => setNewCompany({ ...newCompany, name: e.target.value })}
                      required
                      className="bg-background/50"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="slug">Board Slug</Label>
                    <Input
                      id="slug"
                      placeholder="e.g. openai"
                      value={newCompany.slug}
                      onChange={(e) => setNewCompany({ ...newCompany, slug: e.target.value.toLowerCase() })}
                      required
                      className="bg-background/50"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>Optional Company Quality Signals</Label>
                    <p className="text-xs text-muted-foreground">
                      Keep this explicit. These signals only matter if you also enabled matching strategic preferences in the wizard.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {COMPANY_QUALITY_SIGNAL_OPTIONS.map((signal) => {
                        const isActive = newCompany.companyQualitySignals.includes(signal.value)
                        return (
                          <Badge
                            key={signal.value}
                            variant={isActive ? 'default' : 'outline'}
                            className={cn(
                              'cursor-pointer rounded-xl px-3 py-1.5 h-auto',
                              isActive ? 'bg-primary border-primary' : 'bg-background/40'
                            )}
                            onClick={() => toggleSignals(
                              newCompany.companyQualitySignals,
                              signal.value,
                              (companyQualitySignals) => setNewCompany({ ...newCompany, companyQualitySignals })
                            )}
                          >
                            {signal.label}
                          </Badge>
                        )
                      })}
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        placeholder="Add custom signal"
                        value={newCompanySignal}
                        onChange={(e) => setNewCompanySignal(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key !== 'Enter') return
                          e.preventDefault()
                          const normalized = normalizeCompanyQualitySignal(newCompanySignal)
                          if (!normalized) return
                          setNewCompany({
                            ...newCompany,
                            companyQualitySignals: dedupeCompanyQualitySignals([
                              ...newCompany.companyQualitySignals,
                              normalized,
                            ]),
                          })
                          setNewCompanySignal('')
                        }}
                        className="bg-background/50"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          const normalized = normalizeCompanyQualitySignal(newCompanySignal)
                          if (!normalized) return
                          setNewCompany({
                            ...newCompany,
                            companyQualitySignals: dedupeCompanyQualitySignals([
                              ...newCompany.companyQualitySignals,
                              normalized,
                            ]),
                          })
                          setNewCompanySignal('')
                        }}
                      >
                        Add
                      </Button>
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={isAdding} className="w-full">
                    {isAdding ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Register Slug'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      <Dialog open={!!editingCompany} onOpenChange={(open) => {
        if (!open) {
          setEditingCompany(null)
          setEditingCompanySignal('')
        }
      }}>
        <DialogContent className="border-border/50 bg-background/95 backdrop-blur-xl">
          <form onSubmit={handleUpdateCompany}>
            <DialogHeader>
              <DialogTitle>Edit Company Signals</DialogTitle>
              <DialogDescription>
                Keep company-quality metadata explicit. This does not infer prestige from the company name.
              </DialogDescription>
            </DialogHeader>
            {editingCompany ? (
              <div className="grid gap-4 py-6">
                <div className="grid gap-2">
                  <Label htmlFor="edit-name">Display Name</Label>
                  <Input
                    id="edit-name"
                    value={editingCompany.name}
                    onChange={(e) => setEditingCompany({ ...editingCompany, name: e.target.value })}
                    className="bg-background/50"
                  />
                </div>
                <div className="grid gap-2">
                  <Label>Company Quality Signals</Label>
                  <div className="flex flex-wrap gap-2">
                    {COMPANY_QUALITY_SIGNAL_OPTIONS.map((signal) => {
                      const isActive = editingCompany.companyQualitySignals.includes(signal.value)
                      return (
                        <Badge
                          key={signal.value}
                          variant={isActive ? 'default' : 'outline'}
                          className={cn(
                            'cursor-pointer rounded-xl px-3 py-1.5 h-auto',
                            isActive ? 'bg-primary border-primary' : 'bg-background/40'
                          )}
                          onClick={() => toggleSignals(
                            editingCompany.companyQualitySignals,
                            signal.value,
                            (companyQualitySignals) => setEditingCompany({ ...editingCompany, companyQualitySignals })
                          )}
                        >
                          {signal.label}
                        </Badge>
                      )
                    })}
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Add custom signal"
                      value={editingCompanySignal}
                      onChange={(e) => setEditingCompanySignal(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key !== 'Enter') return
                        e.preventDefault()
                        const normalized = normalizeCompanyQualitySignal(editingCompanySignal)
                        if (!normalized) return
                        setEditingCompany({
                          ...editingCompany,
                          companyQualitySignals: dedupeCompanyQualitySignals([
                            ...editingCompany.companyQualitySignals,
                            normalized,
                          ]),
                        })
                        setEditingCompanySignal('')
                      }}
                      className="bg-background/50"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        const normalized = normalizeCompanyQualitySignal(editingCompanySignal)
                        if (!normalized) return
                        setEditingCompany({
                          ...editingCompany,
                          companyQualitySignals: dedupeCompanyQualitySignals([
                            ...editingCompany.companyQualitySignals,
                            normalized,
                          ]),
                        })
                        setEditingCompanySignal('')
                      }}
                    >
                      Add
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Leave empty to clear company-quality signals for this company.
                  </p>
                </div>
              </div>
            ) : null}
            <DialogFooter>
              <Button type="submit" disabled={isUpdating} className="w-full">
                {isUpdating ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save Company Settings'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <div className="flex-1 flex flex-col gap-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
             placeholder="Search tracked firms..."
             className="pl-10 bg-background/50 border-border/50 backdrop-blur-md"
             value={searchQuery}
             onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center p-32 gap-4 text-muted-foreground">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="animate-pulse font-medium">Synchronizing company lists...</p>
          </div>
        ) : error ? (
           <div className="flex flex-col items-center justify-center p-32 gap-4 text-center">
             <div className="bg-destructive/10 p-4 rounded-full">
               <AlertCircle className="h-10 w-10 text-destructive" />
             </div>
             <div>
               <h2 className="text-xl font-bold">Failed to Load Config</h2>
               <p className="text-muted-foreground text-sm max-w-sm">{error}</p>
             </div>
             <Button onClick={fetchCompanies} variant="outline" size="sm">Try Again</Button>
           </div>
        ) : (
          <Tabs defaultValue="greenhouse" className="w-full">
            <TabsList className="bg-muted/30 p-1 border border-border/50 mb-6 h-12">
              {PLATFORMS.map(p => (
                <TabsTrigger
                  key={p.id}
                  value={p.id}
                  className="px-6 data-[state=active]:bg-background/60 data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all duration-300"
                >
                  {p.name}
                  <Badge variant="secondary" className="ml-2 bg-muted/50 text-[10px] h-4 px-1 opacity-70">
                    {companies ? (companies[p.id]?.length || 0) : 0}
                  </Badge>
                </TabsTrigger>
              ))}
            </TabsList>

            {PLATFORMS.map(p => (
              <TabsContent key={p.id} value={p.id} className="animate-in fade-in slide-in-from-top-2 duration-300">
                {filteredCompanies(p.id).length === 0 ? (
                  <div className="flex flex-col items-center justify-center p-20 border-2 border-dashed border-border/30 rounded-2xl bg-muted/5">
                    <Building2 className="h-10 w-10 text-muted-foreground/30 mb-2" />
                    <p className="text-sm text-muted-foreground font-medium">No {p.name} companies tracked yet.</p>
                    <p className="text-xs text-muted-foreground/60">Click &apos;Add Company Board&apos; to start monitoring boards.</p>
                  </div>
                ) : (
                  <div className="space-y-2 w-full">
                    {filteredCompanies(p.id).map((c) => (
                      <div
                        key={c.slug}
                        className="group relative flex items-center gap-4 px-4 py-3 rounded-xl border border-border/40 bg-card/30 hover:bg-card/60 hover:border-primary/30 transition-all duration-300 shadow-sm backdrop-blur-sm"
                      >
                        {/* Icon */}
                        <div className="flex-shrink-0 bg-primary/10 p-2 rounded-lg text-primary transition-transform group-hover:scale-110 duration-300">
                          <Building2 className="h-5 w-5" />
                        </div>

                        {/* Company info */}
                        <div className="flex-1 min-w-0">
                          <h3 className="font-bold text-base group-hover:text-primary transition-colors leading-tight truncate">
                            {c.name}
                          </h3>
                          <p className="text-xs text-muted-foreground font-mono opacity-70">slug: {c.slug}</p>
                          {c.company_quality_signals?.length ? (
                            <div className="flex flex-wrap gap-1.5 mt-2">
                              {c.company_quality_signals.map((signal) => (
                                <Badge key={signal} variant="outline" className="h-auto rounded-xl bg-primary/5 border-primary/20 text-primary text-[10px] px-2 py-0.5">
                                  <Sparkles className="h-3 w-3 mr-1" />
                                  {getCompanyQualitySignalLabel(signal)}
                                </Badge>
                              ))}
                            </div>
                          ) : null}
                        </div>

                        {/* Platform badge */}
                        <span className="flex-shrink-0 text-[10px] uppercase font-mono tracking-widest text-muted-foreground/70 bg-muted/40 px-1.5 py-0.5 rounded hidden sm:inline">
                          {p.name}
                        </span>

                        <Button
                          variant="ghost"
                          size="icon"
                          className="flex-shrink-0 h-8 w-8 text-muted-foreground hover:text-primary hover:bg-primary/10 opacity-0 group-hover:opacity-100 transition-all"
                          onClick={() => setEditingCompany({
                            platform: p.id,
                            slug: c.slug,
                            name: c.name,
                            companyQualitySignals: dedupeCompanyQualitySignals(c.company_quality_signals || []),
                          })}
                        >
                          <PencilLine className="h-4 w-4" />
                        </Button>

                        {/* Delete button */}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="flex-shrink-0 h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all"
                          onClick={() => handleDelete(p.id, c.slug)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>

                        {/* Hover gradient */}
                        <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                      </div>
                    ))}
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        )}
      </div>
    </div>
  )
}
