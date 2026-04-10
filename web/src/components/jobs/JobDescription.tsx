import React, { useMemo } from 'react'
import { cn } from '@/lib/utils'

interface JobDescriptionProps {
  content?: string | null
  isSparse?: boolean
  className?: string
}

/**
 * Recursive helper to find any field that looks like a description in a JSON object.
 */
function findDescription(obj: unknown): string | null {
  if (!obj || typeof obj !== 'object') return null
  const record = obj as Record<string, unknown>
  
  // Check if this object is a JobPosting or similar
  const isJobPosting = record['@type'] === 'JobPosting' || record.type === 'JobPosting' || 
                       (typeof record['@type'] === 'string' && record['@type'].includes('JobPosting'))
  
  if (isJobPosting && (record.description || record.jobDescription || record.descriptionHtml)) {
     const d = record.description || record.jobDescription || record.descriptionHtml
     if (typeof d === 'string') return d
  }

  // If it's a list, search items
  if (Array.isArray(obj)) {
    for (const item of obj) {
      const res = findDescription(item)
      if (res) return res
    }
  } else {
    // Check for direct keywords first
    const keys = Object.keys(record)
    for (const key of keys) {
      const val = record[key]
      if (key.toLowerCase().includes('description') && typeof val === 'string' && val.length > 100) {
        return val
      }
    }
    // Deep search
    for (const key of keys) {
      const res = findDescription(record[key])
      if (res) return res
    }
  }
  return null
}

/**
 * Resiliently finds and parses JobPosting from any JSON-LD within a blob of text or HTML.
 */
function extractJobDescription(input: string): string | null {
  if (!input) return null
  const trimmed = input.trim()

  // 1. Case: Try to find all <script type="application/ld+json"> blocks
  const scriptRegex = /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi
  const scriptMatches = Array.from(trimmed.matchAll(scriptRegex))
  
  for (const match of scriptMatches) {
     try {
       const rawJson = match[1].trim()
       const parsed = JSON.parse(rawJson)
       const desc = findDescription(parsed)
       if (desc) return desc
     } catch {
       continue
     }
  }

  // 2. Case: The input itself starts with { (might be JSON followed by junk)
  if (trimmed.startsWith('{')) {
    // Try to parse the whole thing first
    try {
      const parsed = JSON.parse(trimmed)
      const desc = findDescription(parsed)
      if (desc) return desc
    } catch {
      // If it fails, try to extract the first balanced { ... } block
      try {
        let depth = 0
        let endIdx = -1
        let inString = false
        for (let i = 0; i < trimmed.length; i++) {
          const char = trimmed.charAt(i)
          if (char === '"' && trimmed.charAt(i-1) !== '\\') {
            inString = !inString
          }
          if (!inString) {
            if (char === '{') depth++
            else if (char === '}') {
              depth--
              if (depth === 0) {
                endIdx = i
                break
              }
            }
          }
        }
        if (endIdx !== -1) {
          const partial = trimmed.substring(0, endIdx + 1)
          const parsed = JSON.parse(partial)
          const desc = findDescription(parsed)
          if (desc) return desc
        }
      } catch {
        // Fall through
      }
    }
  }

  return null
}

/**
 * Decodes common HTML entities.
 */
function decodeHtmlEntities(str: string): string {
  if (!str) return str
  return str
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, ' ')
}

export function JobDescription({ content, isSparse, className }: JobDescriptionProps) {
  const renderedContent = useMemo(() => {
    if (!content) return null

    // 1. Attempt robust JSON extraction first (JSON-LD)
    const extracted = extractJobDescription(content)
    const baseContent = extracted || content

    // 2. Decode entities BEFORE checking for HTML
    // This is crucial because some scrapers return encoded HTML characters like &lt;div&gt;
    const decoded = decodeHtmlEntities(baseContent)

    // 3. Resilient HTML detection
    // Match common tags like <div, <p, <br, <ul, <li, etc.
    const hasHtml = /<[a-z][\s\S]*>/i.test(decoded)

    if (hasHtml) {
      return <div dangerouslySetInnerHTML={{ __html: decoded }} />
    }

    // 4. Fallback to whitespace-pre-wrap for plain text
    return <div className="whitespace-pre-wrap">{decoded}</div>
  }, [content])

  if (!content) {
    return (
      <div className="rounded-[1.5rem] border border-dashed border-border/60 bg-muted/20 p-8 text-center italic text-muted-foreground sm:rounded-3xl sm:p-12">
         <p>The original description was empty or could not be loaded.</p>
         <p className="text-xs mt-2 opacity-60">This can happen if the employer board uses heavy anti-bot protection.</p>
      </div>
    )
  }

  return (
    <div className={cn(
      "prose dark:prose-invert prose-slate max-w-none prose-sm sm:prose-base leading-relaxed selection:bg-primary/20",
      "relative overflow-visible rounded-[1.5rem] border border-border/40 bg-card/60 p-5 shadow-2xl shadow-black/5 backdrop-blur-xl sm:rounded-[2rem] sm:p-8 lg:p-10",
      "prose-headings:text-foreground prose-headings:font-bold prose-p:text-muted-foreground/90 prose-li:text-muted-foreground/90",
      "prose-ul:list-disc prose-ul:pl-6 prose-ol:list-decimal prose-ol:pl-6",
      "prose-li:my-1.5 prose-li:leading-relaxed prose-p:break-words prose-li:break-words prose-pre:overflow-x-auto",
      "prose-strong:text-foreground prose-strong:font-bold",
      "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
      "prose-img:rounded-2xl prose-hr:border-border/30",
      className
    )}>
      {isSparse && (
        <div className="mb-8 p-4 rounded-2xl bg-amber-500/5 border border-amber-500/20 flex items-start gap-4 animate-in fade-in slide-in-from-top-4 duration-500">
          <div className="h-10 w-10 rounded-full bg-amber-500/10 flex items-center justify-center flex-shrink-0 text-xl">
            ⚠️
          </div>
          <div>
            <h4 className="text-amber-600 dark:text-amber-400 font-bold text-sm mb-1">Sparse Posting detected</h4>
            <p className="text-xs text-muted-foreground leading-relaxed italic">
              The AI identified this description as a brief summary or "teaser". 
              Vital details like specific technical requirements or day-to-day responsibilities may be missing from this text.
              Check the original link for the full context before making a decision.
            </p>
          </div>
        </div>
      )}
      {/* Decorative background element */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[100px] -z-10 rounded-full" />
      <div className="absolute bottom-0 left-0 w-64 h-64 bg-primary/5 blur-[100px] -z-10 rounded-full" />
      
      {renderedContent}
    </div>
  )
}
