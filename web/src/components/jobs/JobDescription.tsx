import React, { useMemo } from 'react'
import { cn } from '@/lib/utils'

interface JobDescriptionProps {
  content?: string
  className?: string
}

/**
 * Recursive helper to find any field that looks like a description in a JSON object.
 */
function findDescription(obj: any): string | null {
  if (!obj || typeof obj !== 'object') return null
  
  // Check if this object is a JobPosting or similar
  const isJobPosting = obj['@type'] === 'JobPosting' || obj.type === 'JobPosting' || 
                       (typeof obj['@type'] === 'string' && obj['@type'].includes('JobPosting'))
  
  if (isJobPosting && (obj.description || obj.jobDescription || obj.descriptionHtml)) {
     const d = obj.description || obj.jobDescription || obj.descriptionHtml
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
    const keys = Object.keys(obj)
    for (const key of keys) {
      const val = obj[key]
      if (key.toLowerCase().includes('description') && typeof val === 'string' && val.length > 100) {
        return val
      }
    }
    // Deep search
    for (const key of keys) {
      const res = findDescription(obj[key])
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
     } catch (e) {
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
    } catch (e) {
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
      } catch (innerE) {
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

export function JobDescription({ content, className }: JobDescriptionProps) {
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
      <div className="italic text-muted-foreground p-12 text-center bg-muted/20 rounded-3xl border border-dashed border-border/60">
         <p>The original description was empty or could not be loaded.</p>
         <p className="text-xs mt-2 opacity-60">This can happen if the employer board uses heavy anti-bot protection.</p>
      </div>
    )
  }

  return (
    <div className={cn(
      "prose dark:prose-invert prose-slate max-w-none prose-sm sm:prose-base leading-relaxed selection:bg-primary/20",
      "bg-card/60 backdrop-blur-xl p-8 sm:p-10 rounded-[2rem] border border-border/40 shadow-2xl shadow-black/5 relative overflow-visible",
      "prose-headings:text-foreground prose-headings:font-bold prose-p:text-muted-foreground/90 prose-li:text-muted-foreground/90",
      "prose-ul:list-disc prose-ul:pl-6 prose-ol:list-decimal prose-ol:pl-6",
      "prose-li:my-1.5 prose-li:leading-relaxed",
      "prose-strong:text-foreground prose-strong:font-bold",
      "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
      "prose-img:rounded-2xl prose-hr:border-border/30",
      className
    )}>
      {/* Decorative background element */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[100px] -z-10 rounded-full" />
      <div className="absolute bottom-0 left-0 w-64 h-64 bg-primary/5 blur-[100px] -z-10 rounded-full" />
      
      {renderedContent}
    </div>
  )
}
