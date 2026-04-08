import createClient from 'openapi-fetch'
import type { paths } from './types'

export const api = createClient<paths>({
  // Use direct backend URL in dev to avoid proxy-level socket hang ups during long AI analysis
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
})
