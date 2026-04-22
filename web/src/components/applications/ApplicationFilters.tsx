'use client'

import { Search, SlidersHorizontal } from 'lucide-react'

const GROUP_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'offers', label: 'Offers' },
  { value: 'closed', label: 'Closed' },
  { value: 'all', label: 'All' },
] as const

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'applied', label: 'Applied' },
  { value: 'screening', label: 'Screening' },
  { value: 'interviewing', label: 'Interviewing' },
  { value: 'offer', label: 'Offer' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected_by_company', label: 'Rejected by Company' },
  { value: 'rejected_by_user', label: 'Withdrawn' },
  { value: 'ghosted', label: 'Ghosted' },
] as const

export type ApplicationGroup = (typeof GROUP_OPTIONS)[number]['value']

interface ApplicationFiltersProps {
  group: ApplicationGroup
  status: string
  searchTerm: string
  sort: string
  onGroupChange: (value: ApplicationGroup) => void
  onStatusChange: (value: string) => void
  onSearchTermChange: (value: string) => void
  onSortChange: (value: string) => void
}

export function ApplicationFilters({
  group,
  status,
  searchTerm,
  sort,
  onGroupChange,
  onStatusChange,
  onSearchTermChange,
  onSortChange,
}: ApplicationFiltersProps) {
  return (
    <div className="space-y-4 rounded-3xl border border-border/40 bg-card/30 p-4 shadow-sm backdrop-blur-sm">
      <div className="flex flex-wrap items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
        {GROUP_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => onGroupChange(option.value)}
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-all ${
              group === option.value
                ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                : 'border-border/50 bg-background/40 text-muted-foreground hover:border-primary/30 hover:text-foreground'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_200px_220px]">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchTerm}
            onChange={(event) => onSearchTermChange(event.target.value)}
            placeholder="Search title, company, or notes..."
            className="h-12 w-full rounded-2xl border border-border/50 bg-background/60 pl-11 pr-4 text-sm font-medium outline-none transition-all focus:border-primary/40 focus:ring-4 focus:ring-primary/5"
          />
        </label>

        <select
          value={status}
          onChange={(event) => onStatusChange(event.target.value)}
          className="h-12 rounded-2xl border border-border/50 bg-background/60 px-4 text-sm font-medium outline-none transition-all focus:border-primary/40 focus:ring-4 focus:ring-primary/5"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value || 'all'} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select
          value={sort}
          onChange={(event) => onSortChange(event.target.value)}
          className="h-12 rounded-2xl border border-border/50 bg-background/60 px-4 text-sm font-medium outline-none transition-all focus:border-primary/40 focus:ring-4 focus:ring-primary/5"
        >
          <option value="next_stage_date">Sort: Next Stage</option>
          <option value="applied_date">Sort: Applied Date</option>
          <option value="company">Sort: Company</option>
          <option value="status">Sort: Status</option>
        </select>
      </div>
    </div>
  )
}
