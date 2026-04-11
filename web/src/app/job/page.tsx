'use client'

import { Suspense } from 'react'
import { Loader2 } from 'lucide-react'
import { useSearchParams } from 'next/navigation'
import { JobDetailView } from '@/components/jobs/JobDetailView'

function LegacyJobDetailPageContent() {
  const searchParams = useSearchParams()
  const rawJobId = searchParams.get('id')
  const boardHref = searchParams.get('from') || '/jobs'
  const jobId = rawJobId ? parseInt(rawJobId, 10) : null

  return <JobDetailView jobId={Number.isFinite(jobId) ? jobId : null} boardHref={boardHref} />
}

export default function LegacyJobDetailPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen flex-col items-center justify-center gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground animate-pulse">Consulting the radar matching engine...</p>
      </div>
    }>
      <LegacyJobDetailPageContent />
    </Suspense>
  )
}
