'use client'

import { useEffect, useMemo, useState } from 'react'
import type { components } from '@/lib/api/types'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { ExternalLink, FilePenLine, Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

type ImportJobResponse = components['schemas']['ImportJobResponse']
type CompaniesResponse = components['schemas']['CompaniesResponse']

type Mode = 'url' | 'manual'

type TrackableCompany = {
  platform: 'greenhouse' | 'lever' | 'ashby' | 'workable' | 'bamboohr' | 'smartrecruiters'
  slug: string
  name: string
}

function titleizeSlug(slug: string) {
  return slug
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function resolveTrackableCompany(url: string, fallbackName?: string): TrackableCompany | null {
  const trimmed = url.trim()
  if (!trimmed) return null

  let parsed: URL
  try {
    parsed = new URL(trimmed)
  } catch {
    return null
  }

  const host = parsed.hostname.toLowerCase()
  const segments = parsed.pathname.split('/').filter(Boolean)
  const makeCompany = (platform: TrackableCompany['platform'], slug?: string | null) => {
    if (!slug) return null
    const normalizedSlug = slug.trim().toLowerCase()
    if (!normalizedSlug) return null
    return {
      platform,
      slug: normalizedSlug,
      name: fallbackName?.trim() || titleizeSlug(normalizedSlug),
    } satisfies TrackableCompany
  }

  if (host.includes('greenhouse.io')) {
    return makeCompany('greenhouse', segments[0])
  }
  if (host === 'jobs.lever.co') {
    return makeCompany('lever', segments[0])
  }
  if (host === 'jobs.ashbyhq.com') {
    return makeCompany('ashby', segments[0])
  }
  if (host === 'apply.workable.com') {
    return makeCompany('workable', segments[0])
  }
  if (host.endsWith('.bamboohr.com')) {
    return makeCompany('bamboohr', host.split('.')[0])
  }
  if (host === 'jobs.smartrecruiters.com' || host === 'careers.smartrecruiters.com') {
    return makeCompany('smartrecruiters', segments[0])
  }

  return null
}

function emptyForm() {
  return {
    url: '',
    company_name: '',
    title: '',
    location: '',
    applied_at: '',
    description: '',
    salary: '',
    notes: '',
    track_company_in_pipeline: false,
  }
}

export function ImportJobDialog({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImported: (jobId?: number | null) => Promise<void> | void
}) {
  const [mode, setMode] = useState<Mode>('url')
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState(emptyForm())
  const [trackedCompanies, setTrackedCompanies] = useState<CompaniesResponse | null>(null)

  useEffect(() => {
    if (!open) {
      setMode('url')
      setSubmitting(false)
      setForm(emptyForm())
      setTrackedCompanies(null)
    }
  }, [open])

  useEffect(() => {
    if (!open) return

    let cancelled = false
    void (async () => {
      const { data, error } = await api.GET('/api/companies/{profile}', {
        params: { path: { profile: 'default' } },
      })
      if (cancelled || error || !data) return
      setTrackedCompanies(data)
    })()

    return () => {
      cancelled = true
    }
  }, [open])

  const canSubmitUrl = useMemo(() => form.url.trim().length > 0, [form.url])
  const canSubmitManual = useMemo(
    () => form.company_name.trim().length > 0 && form.title.trim().length > 0,
    [form.company_name, form.title]
  )
  const trackableCompany = useMemo(
    () => resolveTrackableCompany(form.url, form.company_name),
    [form.company_name, form.url]
  )
  const companyAlreadyTracked = useMemo(() => {
    if (!trackableCompany || !trackedCompanies) return false
    const entries = trackedCompanies[trackableCompany.platform] ?? []
    return entries.some((entry) => entry.slug === trackableCompany.slug)
  }, [trackableCompany, trackedCompanies])
  const showTrackCompanyOption = Boolean(trackableCompany && !companyAlreadyTracked)

  useEffect(() => {
    if (showTrackCompanyOption) return
    setForm((prev) => (
      prev.track_company_in_pipeline
        ? { ...prev, track_company_in_pipeline: false }
        : prev
    ))
  }, [showTrackCompanyOption])

  const finishImport = async (response: ImportJobResponse, successMessage: string) => {
    await onImported(response.job_id)
    onOpenChange(false)
    toast.success(successMessage, {
      description: response.already_tracked ? 'This job was already in your tracker.' : undefined,
    })
  }

  const submitUrlImport = async () => {
    if (!canSubmitUrl) return

    setSubmitting(true)
    try {
      const { data, error } = await api.POST('/api/applications/import', {
        body: {
          url: form.url.trim(),
          applied_at: form.applied_at || undefined,
          notes: form.notes.trim() || undefined,
          track_company_in_pipeline: showTrackCompanyOption ? form.track_company_in_pipeline : false,
        },
      })
      if (error || !data) throw new Error('Failed to import application')

      if (data.needs_manual_entry) {
        setMode('manual')
        toast.message('Automatic fetch was not available for this URL. Fill in the basics to add it manually.')
        return
      }

      await finishImport(data, data.already_tracked ? 'Application already tracked' : 'Application imported')
    } catch (err: any) {
      toast.error(err.message || 'Failed to import application')
    } finally {
      setSubmitting(false)
    }
  }

  const submitManualImport = async () => {
    if (!canSubmitManual) return

    setSubmitting(true)
    try {
      let response: ImportJobResponse | undefined

      if (mode === 'manual' && form.url.trim()) {
        const { data, error } = await api.POST('/api/applications/import', {
          body: {
            url: form.url.trim(),
            company_name: form.company_name.trim(),
            title: form.title.trim(),
            location: form.location.trim() || undefined,
            applied_at: form.applied_at || undefined,
            notes: form.notes.trim() || undefined,
            track_company_in_pipeline: showTrackCompanyOption ? form.track_company_in_pipeline : false,
          },
        })
        if (error || !data) throw new Error('Failed to import application')
        response = data
      } else {
        const { data, error } = await api.POST('/api/applications/import/manual', {
          body: {
            url: form.url.trim() || undefined,
            company_name: form.company_name.trim(),
            title: form.title.trim(),
            location: form.location.trim() || undefined,
            applied_at: form.applied_at || undefined,
            description: form.description.trim() || undefined,
            salary: form.salary.trim() || undefined,
            notes: form.notes.trim() || undefined,
            track_company_in_pipeline: showTrackCompanyOption ? form.track_company_in_pipeline : false,
          },
        })
        if (error || !data) throw new Error('Failed to create manual application')
        response = data
      }

      await finishImport(response, response.already_tracked ? 'Application already tracked' : 'Application added to tracker')
    } catch (err: any) {
      toast.error(err.message || 'Failed to add application')
    } finally {
      setSubmitting(false)
    }
  }

  const showUrlFields = mode === 'url'
  const showManualFields = mode === 'manual'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-[96vw] rounded-3xl border border-border/50 bg-popover/95 p-0 shadow-2xl backdrop-blur-xl sm:max-w-5xl"
        showCloseButton
      >
        <DialogHeader className="px-6 pt-6">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">Import Application</span>
          </div>
          <DialogTitle className="text-2xl font-black tracking-tight">Add an external application</DialogTitle>
          <DialogDescription>
            Paste a job URL and we&apos;ll try to import it automatically. If the source can&apos;t be fetched, you can finish it manually without leaving the dialog.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 px-6 pb-6">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setMode('url')}
              className={cn(
                'rounded-full border px-3 py-1.5 text-xs font-semibold transition-all',
                mode === 'url'
                  ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                  : 'border-border/50 bg-background/40 text-muted-foreground hover:border-primary/30 hover:text-foreground'
              )}
            >
              Import from URL
            </button>
            <button
              onClick={() => setMode('manual')}
              className={cn(
                'rounded-full border px-3 py-1.5 text-xs font-semibold transition-all',
                mode === 'manual'
                  ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                  : 'border-border/50 bg-background/40 text-muted-foreground hover:border-primary/30 hover:text-foreground'
              )}
            >
              Enter manually
            </button>
          </div>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="import-url">Job URL</Label>
                <Input
                  id="import-url"
                  value={form.url}
                  onChange={(event) => setForm((prev) => ({ ...prev, url: event.target.value }))}
                  placeholder="https://boards.greenhouse.io/company/jobs/12345"
                  className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
                />
                <p className="text-xs text-muted-foreground">
                  Supported URLs can be imported directly. Unsupported URLs can still be added with manual details.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="import-applied-at">Applied on</Label>
                <Input
                  id="import-applied-at"
                  type="date"
                  value={form.applied_at}
                  onChange={(event) => setForm((prev) => ({ ...prev, applied_at: event.target.value }))}
                  className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
                />
                <p className="text-xs text-muted-foreground">
                  Optional. Use this when adding jobs you applied to earlier. Leave blank to use today.
                </p>
              </div>

              {showManualFields && (
                <>
                  <Separator />
                  <div className="grid gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="import-company">Company Name</Label>
                      <Input
                        id="import-company"
                        value={form.company_name}
                        onChange={(event) => setForm((prev) => ({ ...prev, company_name: event.target.value }))}
                        placeholder="Acme Corp"
                        className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="import-title">Job Title</Label>
                      <Input
                        id="import-title"
                        value={form.title}
                        onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                        placeholder="Senior QA Engineer"
                        className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
                      />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="import-location">Location</Label>
                        <Input
                          id="import-location"
                          value={form.location}
                          onChange={(event) => setForm((prev) => ({ ...prev, location: event.target.value }))}
                          placeholder="Remote, Berlin, Warsaw..."
                          className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="import-salary">Salary</Label>
                        <Input
                          id="import-salary"
                          value={form.salary}
                          onChange={(event) => setForm((prev) => ({ ...prev, salary: event.target.value }))}
                          placeholder="$140k - $160k"
                          className="h-11 rounded-2xl border-border/50 bg-background/50 px-4"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="import-description">Description</Label>
                      <Textarea
                        id="import-description"
                        value={form.description}
                        onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                        placeholder="Optional notes from the posting, recruiter message, or copied job description..."
                        className="min-h-28 rounded-2xl border-border/50 bg-background/50 px-4 py-3"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className="space-y-4 rounded-3xl border border-border/40 bg-background/35 p-4">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-primary">
                  <FilePenLine className="h-3.5 w-3.5" />
                  Notes
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Keep recruiter context, where you found the role, or follow-up reminders attached from the moment you add it.
                </p>
              </div>
              <Textarea
                value={form.notes}
                onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
                placeholder="Found on LinkedIn, recruiter reached out, referred by ex-teammate..."
                className="min-h-40 rounded-2xl border-border/50 bg-background/50 px-4 py-3"
              />

              {showTrackCompanyOption && trackableCompany && (
                <label className="flex items-start gap-3 rounded-2xl border border-border/40 bg-background/40 px-4 py-3">
                  <Checkbox
                    checked={form.track_company_in_pipeline}
                    onCheckedChange={(checked) => setForm((prev) => ({ ...prev, track_company_in_pipeline: checked === true }))}
                    className="mt-0.5"
                  />
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-foreground">
                      Track {trackableCompany.name} in the pipeline
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      Add this company board to future pipeline runs so new roles from {trackableCompany.name} can show up automatically.
                    </p>
                  </div>
                </label>
              )}

              {showManualFields && form.url.trim() && (
                <a
                  href={form.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-xs font-medium text-primary hover:underline"
                >
                  Open source URL <ExternalLink className="h-3.5 w-3.5" />
                </a>
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="mx-0 mb-0 rounded-b-3xl border-t border-border/40 bg-background/30 px-6 py-4 backdrop-blur-sm">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          {showUrlFields ? (
            <Button onClick={() => void submitUrlImport()} disabled={!canSubmitUrl || submitting} className="gap-2">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Fetch Job Details
            </Button>
          ) : (
            <Button onClick={() => void submitManualImport()} disabled={!canSubmitManual || submitting} className="gap-2">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePenLine className="h-4 w-4" />}
              Add to Tracker
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
