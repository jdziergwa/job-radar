import createClient from 'openapi-fetch'
import { IS_DEMO } from '@/lib/demo-mode'
import { API_BASE_URL } from './base-url'
import { demoFetch } from './demo-fetch'
import type { paths } from './types'

export const api = createClient<paths>({
  baseUrl: IS_DEMO ? '' : API_BASE_URL,
  ...(IS_DEMO ? { fetch: demoFetch } : {}),
})
