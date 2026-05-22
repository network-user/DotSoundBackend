const MINI_APP_ROOT = '/mini_app'

function normalizeMiniAppPath(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, '') || '/'
  if (trimmed === MINI_APP_ROOT || trimmed.startsWith(`${MINI_APP_ROOT}/`)) {
    return trimmed
  }
  if (trimmed.startsWith('/profile/') || trimmed.startsWith('/artist/')) {
    return `${MINI_APP_ROOT}${trimmed}`
  }
  return trimmed
}

export function resolvePublicProfileUrl(
  profileUrl: string | null | undefined,
  userId: number,
): string {
  const raw = (profileUrl || '').trim()
  if (raw.startsWith('http://') || raw.startsWith('https://')) {
    try {
      const parsed = new URL(raw)
      parsed.pathname = normalizeMiniAppPath(parsed.pathname)
      return parsed.toString()
    } catch {
      return raw
    }
  }
  const origin =
    typeof window !== 'undefined' ? window.location.origin : ''
  const base = `${origin}${MINI_APP_ROOT}`.replace(/\/$/, '')
  if (raw.startsWith('/')) {
    const path = normalizeMiniAppPath(raw)
    return `${origin}${path}`
  }
  return `${base}/profile/${userId}`
}

export function resolvePublicArtistUrl(
  profileUrl: string | null | undefined,
  artistId: number,
): string {
  const raw = (profileUrl || '').trim()
  if (raw.startsWith('http://') || raw.startsWith('https://')) {
    try {
      const parsed = new URL(raw)
      parsed.pathname = normalizeMiniAppPath(parsed.pathname)
      return parsed.toString()
    } catch {
      return raw
    }
  }
  const origin =
    typeof window !== 'undefined' ? window.location.origin : ''
  const base = `${origin}${MINI_APP_ROOT}`.replace(/\/$/, '')
  if (raw.startsWith('/')) {
    const path = normalizeMiniAppPath(raw)
    return `${origin}${path}`
  }
  return `${base}/artist/${artistId}`
}
