import type { components } from '@/lib/api/types'

export type ApplicationStatus = components['schemas']['ApplicationStatusUpdate']['application_status']
export type ApplicationEventResponse = components['schemas']['ApplicationEventResponse']

type ApplicationStageMeta = {
  label: string
  badge: string
  dot: string
}

export const APPLICATION_STAGE_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  applied: ['screening', 'interviewing', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  screening: ['applied', 'interviewing', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  interviewing: ['screening', 'offer', 'rejected_by_company', 'rejected_by_user', 'ghosted'],
  offer: ['interviewing', 'accepted', 'rejected_by_user'],
  accepted: ['offer', 'rejected_by_user'],
  rejected_by_company: ['applied'],
  rejected_by_user: ['applied'],
  ghosted: ['screening', 'interviewing'],
}

export const APPLICATION_STAGE_META: Record<ApplicationStatus, ApplicationStageMeta> = {
  applied: {
    label: 'Applied',
    badge: 'border-sky-500/20 bg-sky-500/10 text-sky-700 dark:text-sky-300',
    dot: 'bg-sky-500',
  },
  screening: {
    label: 'Screening',
    badge: 'border-cyan-500/20 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
    dot: 'bg-cyan-500',
  },
  interviewing: {
    label: 'Interviewing',
    badge: 'border-indigo-500/20 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300',
    dot: 'bg-indigo-500',
  },
  offer: {
    label: 'Offer',
    badge: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    dot: 'bg-emerald-500',
  },
  accepted: {
    label: 'Accepted',
    badge: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    dot: 'bg-emerald-600',
  },
  rejected_by_company: {
    label: 'Rejected',
    badge: 'border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300',
    dot: 'bg-rose-500',
  },
  rejected_by_user: {
    label: 'Withdrawn',
    badge: 'border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-300',
    dot: 'bg-orange-500',
  },
  ghosted: {
    label: 'Ghosted',
    badge: 'border-slate-500/20 bg-slate-500/10 text-slate-700 dark:text-slate-300',
    dot: 'bg-slate-500',
  },
}

export const APPLICATION_STAGE_OPTIONS = (Object.entries(APPLICATION_STAGE_META) as Array<[ApplicationStatus, ApplicationStageMeta]>)
  .map(([value, meta]) => ({
    value,
    label: meta.label,
  }))

export function getApplicationStageLabel(status: string | null | undefined): string {
  if (!status) return ''

  return APPLICATION_STAGE_META[status as ApplicationStatus]?.label
    ?? status.replaceAll('_', ' ').replace(/\b\w/g, (match) => match.toUpperCase())
}

export function getApplicationStageMeta(status: string | null | undefined): ApplicationStageMeta {
  return APPLICATION_STAGE_META[status as ApplicationStatus] ?? {
    label: getApplicationStageLabel(status),
    badge: 'border-primary/20 bg-primary/10 text-primary',
    dot: 'bg-primary',
  }
}

export function getNextApplicationStage(status: ApplicationStatus): ApplicationStatus {
  return APPLICATION_STAGE_TRANSITIONS[status]?.[0] ?? 'screening'
}

export function getApplicationEventDate(event: Pick<ApplicationEventResponse, 'occurred_at' | 'created_at'>): string {
  return event.occurred_at || event.created_at
}

export function normalizeTrackerDateForInput(value?: string | null): string {
  if (!value) return ''
  return value.includes('T') ? value.slice(0, 10) : value
}

export function getTodayDateInputValue(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
