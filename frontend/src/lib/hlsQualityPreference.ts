// Persistent user preference for HLS variant selection.
//
// 'auto' (default): network-aware. PrefetchManager picks 'hi' on
// fast connections (>=5 Mbps, save-data off), otherwise 'lo'.
// hls.js startLevel stays at -1 so its built-in ABR can up-/downshift.
//
// 'lo' / 'hi': hard override. PrefetchManager always warms the named
// variant first; hls.js startLevel is pinned to that variant's index
// so playback starts at the chosen quality and never auto-switches.
//
// Stored in localStorage so it survives page reloads but never leaves
// the device (no backend round-trip, no telemetry).

export type HlsQualityPreference = 'auto' | 'lo' | 'hi'

const STORAGE_KEY = 'setting-hls-quality'

function _isPreference(value: unknown): value is HlsQualityPreference {
  return value === 'auto' || value === 'lo' || value === 'hi'
}

export function getHlsQualityPreference(): HlsQualityPreference {
  if (typeof localStorage === 'undefined') return 'auto'
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (_isPreference(v)) return v
  } catch {
    /* localStorage may be blocked (Safari private mode) */
  }
  return 'auto'
}

export function setHlsQualityPreference(
  value: HlsQualityPreference,
): void {
  if (typeof localStorage === 'undefined') return
  try {
    if (value === 'auto') {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, value)
    }
  } catch {
    /* localStorage may be blocked */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent<HlsQualityPreference>('dotsound:hls-quality', {
        detail: value,
      }),
    )
  }
}

export function subscribeHlsQualityPreference(
  cb: (value: HlsQualityPreference) => void,
): () => void {
  if (typeof window === 'undefined') return () => {}
  const onCustom = (e: Event) => {
    const ce = e as CustomEvent<HlsQualityPreference>
    if (_isPreference(ce.detail)) cb(ce.detail)
  }
  const onStorage = (e: StorageEvent) => {
    if (e.key !== STORAGE_KEY) return
    cb(getHlsQualityPreference())
  }
  window.addEventListener('dotsound:hls-quality', onCustom)
  window.addEventListener('storage', onStorage)
  return () => {
    window.removeEventListener('dotsound:hls-quality', onCustom)
    window.removeEventListener('storage', onStorage)
  }
}
