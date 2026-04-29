const STORAGE_PREFIX = 'dotsound-third-party-stream-url:'

export function getThirdPartyStreamOverride(
  trackId: number,
): string | null {
  try {
    const raw = sessionStorage.getItem(
      STORAGE_PREFIX + String(trackId),
    )
    const u = raw?.trim()
    if (!u) return null
    if (!/^https?:\/\//i.test(u)) return null
    return u
  } catch {
    return null
  }
}

export function setThirdPartyStreamOverride(
  trackId: number,
  url: string,
): void {
  sessionStorage.setItem(
    STORAGE_PREFIX + String(trackId),
    url.trim(),
  )
}

export function clearThirdPartyStreamOverride(
  trackId: number,
): void {
  sessionStorage.removeItem(
    STORAGE_PREFIX + String(trackId),
  )
}

export function inferStreamTypeFromUrl(
  url: string,
): 'hls' | 'direct' {
  const lower = url.toLowerCase()
  if (lower.includes('.m3u8')) return 'hls'
  return 'direct'
}
