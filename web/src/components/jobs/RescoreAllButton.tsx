'use client'

import { useState } from 'react'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { RefreshCw, Play, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface RescoreAllButtonProps {
  variant?: 'default' | 'outline' | 'secondary' | 'ghost'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  className?: string
  showText?: boolean
}

export function RescoreAllButton({ 
  variant = 'outline', 
  size = 'sm', 
  className = '',
  showText = true
}: RescoreAllButtonProps) {
  const [loading, setLoading] = useState(false)

  const handleRescoreAll = async () => {
    const confirmed = window.confirm(
      "Rescore all jobs? This will re-evaluate every job using the current profile and AI scoring. It may take several minutes."
    )
    
    if (!confirmed) return

    setLoading(true)
    try {
      // @ts-ignore - fixing argument count lint
      const { data, error } = await api.POST('/api/jobs/rescore/all', { 
        params: { query: { profile: 'default' } } 
      })
      
      if (error) {
        toast.error('Failed to start bulk rescore')
        console.error('Rescore all error:', error)
      } else {
        toast.success('Bulk rescore started in background')
        // Dispatch event for other components to listen (like page.tsx poller)
        window.dispatchEvent(new CustomEvent('pipeline-started', { 
          detail: { run_id: (data as any)?.run_id } 
        }))
      }
    } catch (err) {
      toast.error('An unexpected error occurred')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const buttonContent = (
    <Button
      variant={variant}
      size={size}
      onClick={handleRescoreAll}
      disabled={loading}
      className={`gap-2 ${className}`}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <RefreshCw className="h-4 w-4" />
      )}
      {showText && (loading ? 'Rescoring...' : 'Rescore All')}
    </Button>
  )

  if (!showText) {
    return (
      <Tooltip>
        <TooltipTrigger>
          {buttonContent}
        </TooltipTrigger>
        <TooltipContent align="center" side="top">
          Rescore all jobs in background
        </TooltipContent>
      </Tooltip>
    )
  }

  return buttonContent
}
