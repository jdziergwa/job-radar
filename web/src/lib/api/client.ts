import createClient from 'openapi-fetch'
import { IS_DEMO } from '@/lib/demo-mode'
import { demoFetch } from './demo-fetch'
import type { paths } from './types'

export const api = createClient<paths>({
  baseUrl: IS_DEMO ? '' : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'),
  ...(IS_DEMO ? { fetch: demoFetch } : {}),
})
