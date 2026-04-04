'use client'

import React, { useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Building2, ArrowUpDown, TrendingUp } from 'lucide-react'

export function CompanyTable({ data }: { data: any[] }) {
  const [sortKey, setSortKey] = useState<'job_count' | 'avg_score'>('job_count')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  const toggleSort = (key: 'job_count' | 'avg_score') => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortOrder('desc')
    }
  }

  const sortedData = [...data].sort((a, b) => {
    const valA = a[sortKey] || 0
    const valB = b[sortKey] || 0
    return sortOrder === 'asc' ? valA - valB : valB - valA
  })

  return (
    <Card className="border-border/50 bg-background/30 backdrop-blur-md">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Building2 className="h-4 w-4 text-primary" />
            Company Activity
          </CardTitle>
          <CardDescription className="text-xs mt-1">Aggregated performance by hiring organization</CardDescription>
        </div>
        <Badge variant="secondary" className="text-[10px] font-mono opacity-60">
          Showing Top {data.length}
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border border-border/30 overflow-hidden">
          <Table>
            <TableHeader className="bg-muted/30">
              <TableRow className="hover:bg-transparent border-border/30">
                <TableHead className="font-semibold text-xs py-2">Organization</TableHead>
                <TableHead 
                  className="font-semibold text-xs text-center cursor-pointer hover:text-foreground transition-colors py-2"
                  onClick={() => toggleSort('job_count')}
                >
                  <div className="flex items-center justify-center gap-1">
                    Postings <ArrowUpDown className="h-3 w-3" />
                  </div>
                </TableHead>
                <TableHead 
                  className="font-semibold text-xs text-center cursor-pointer hover:text-foreground transition-colors py-2"
                  onClick={() => toggleSort('avg_score')}
                >
                  <div className="flex items-center justify-center gap-1">
                    Avg Score <ArrowUpDown className="h-3 w-3" />
                  </div>
                </TableHead>
                <TableHead className="font-semibold text-xs text-right py-2">Last Seen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedData.map((company) => (
                <TableRow key={company.company_name} className="border-border/20 group hover:bg-primary/5 transition-colors">
                  <TableCell className="font-medium text-xs py-3 max-w-[180px] truncate">
                    {company.company_name}
                  </TableCell>
                  <TableCell className="text-center font-mono text-xs py-3">
                    {company.job_count}
                  </TableCell>
                  <TableCell className="text-center py-3">
                    {company.avg_score ? (
                      <div className="flex items-center justify-center gap-1.5">
                        <span className={`font-bold text-xs ${
                          company.avg_score >= 80 ? 'text-score-high' :
                          company.avg_score >= 60 ? 'text-score-medium' :
                          'text-score-low'
                        }`}>
                          {Math.round(company.avg_score)}%
                        </span>
                        {company.avg_score >= 70 && (
                          <TrendingUp className="h-3 w-3 text-emerald-500 opacity-50 group-hover:opacity-100 transition-opacity" />
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground/40">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-[10px] text-muted-foreground uppercase py-3 whitespace-nowrap">
                    {company.last_seen ? new Date(company.last_seen).toLocaleDateString() : '—'}
                  </TableCell>
                </TableRow>
              ))}
              {sortedData.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-muted-foreground italic text-xs">
                    Insufficient data for company aggregation.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
