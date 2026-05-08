import { getAdminApiPath } from '@/lib/adminPath'

export function readCsrfCookie(): string {
  const match = document.cookie.match(
    /(?:^|; )admin_csrf=([^;]+)/,
  )
  return match ? decodeURIComponent(match[1]) : ''
}

export async function ensureCsrf(
  fetcher: typeof fetch = fetch,
): Promise<string> {
  const existing = readCsrfCookie()
  if (existing) return existing
  await fetcher(getAdminApiPath('/auth/csrf'), {
    credentials: 'include',
  })
  return readCsrfCookie()
}
