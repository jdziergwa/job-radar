'use client'

import { useState, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Upload, FileUp, X, AlertCircle, FileText, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api/client'

import { WizardData } from '../types'

import { StepProps } from '../types'

export function UploadCV({ onNext, onBack, onUpdate, data }: StepProps) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(data?.error || null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (selectedFile: File) => {
    setError(null)
    if (selectedFile.type !== 'application/pdf') {
      setError('Only PDF files are supported.')
      return
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError('File is too large. Maximum size is 10MB.')
      return
    }
    setFile(selectedFile)
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) handleFileSelect(droppedFile)
  }

  const handleUpload = async () => {
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    // Trigger analysis and move to loading step
    const analysisPromise = api.POST('/api/wizard/analyze-cv', {
      body: formData as any // openapi-fetch handled FormData via BodyInit
    })

    onNext({ analysisPromise, cvFile: { name: file.name, size: file.size } })
  }

  return (
    <div className="flex flex-col gap-4 py-2 animate-in fade-in slide-in-from-bottom-4 duration-500 w-full">
      <div className="text-center space-y-1 bg-background/50 py-4 -mt-4 border-b border-border/10 mb-2 w-full">
        <h2 className="text-xl font-bold tracking-tight">Upload CV (PDF)</h2>
        <p className="text-muted-foreground text-xs max-w-sm mx-auto">We'll use AI to extract your skills and expertise from your PDF.</p>
      </div>

      <div className="space-y-4">
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "relative group cursor-pointer flex flex-col items-center justify-center gap-4 py-8 px-8 rounded-[2rem] border-2 border-dashed transition-all duration-300 bg-background/50 backdrop-blur-sm",
            isDragging 
              ? "border-primary bg-primary/5 scale-[1.01] shadow-2xl shadow-primary/10" 
              : "border-border/50 hover:border-primary/50 hover:bg-muted/30"
          )}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
            accept=".pdf"
            className="hidden"
          />

          <div className={cn(
            "p-4 rounded-2xl transition-all duration-500 shadow-sm",
            file 
              ? "bg-emerald-500/20 text-emerald-500 ring-2 ring-emerald-500/20" 
              : "bg-primary/10 text-primary group-hover:bg-primary group-hover:text-white"
          )}>
            {file ? <FileText className="h-8 w-8 animate-in zoom-in duration-300" /> : <Upload className="h-8 w-8 group-hover:-translate-y-1 transition-transform" />}
          </div>

          <div className="text-center space-y-2">
            {file ? (
              <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                <p className="font-bold text-lg truncate max-w-[280px]">{file.name}</p>
                <p className="text-xs font-mono text-muted-foreground/60">
                    {(file.size / 1024 / 1024).toFixed(2)} MB &bull; READY TO ANALYZE
                </p>
              </div>
            ) : (
              <>
                <p className="font-bold text-lg">Drop your CV here or click to browse</p>
                <p className="text-sm text-muted-foreground">PDF files only &bull; Max 10MB</p>
              </>
            )
          }
          </div>

          {file && (
            <button 
              onClick={(e) => { e.stopPropagation(); setFile(null); }}
              className="absolute top-6 right-6 p-2 rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-4 p-4 rounded-2xl bg-destructive/10 border border-destructive/20 text-destructive text-sm animate-in zoom-in-95 duration-300">
            <div className="bg-destructive/20 p-2 rounded-lg">
                <AlertCircle className="h-4 w-4" />
            </div>
            <p className="font-medium text-left">{error}</p>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2 mt-2">
        <Button 
          onClick={handleUpload} 
          disabled={!file} 
          className="h-12 text-base font-bold shadow-xl gap-2 rounded-2xl hover:scale-[1.01] active:scale-[0.99] transition-all"
        >
          Analyze CV & Continue
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button onClick={() => onBack()} variant="ghost" size="sm" className="text-muted-foreground hover:bg-muted/50 rounded-xl h-10">
          Back
        </Button>
      </div>
    </div>
  )
}
