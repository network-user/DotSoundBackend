import type { StreamResponse } from '@/types/api'

export type PlaybackCacheWarmAction =
  | 'idb_download'
  | 'progressive_sw'
  | 'skip'

export type PrefetchedStreamRecord = {
  trackId: number
  url: string
  streamType: 'direct' | 'hls'
  expiresAt: number | null
  resolvedAt: number
}

export function choosePlaybackCacheWarmAction(
  track: {
    access_mode?: string | null
    catalog_type?: string | null
  },
  state: {
    isIdbCached: boolean
    isProgressiveSwCached: boolean
    usesInternalHls: boolean
  },
): PlaybackCacheWarmAction {
  if (state.isIdbCached) return 'skip'
  if (
    track.access_mode === 'official_embed' ||
    track.access_mode === 'external_link'
  ) {
    return 'skip'
  }
  if (
    track.access_mode === 'internal_stream' &&
    track.catalog_type !== 'external_reference'
  ) {
    return 'idb_download'
  }
  if (state.usesInternalHls) return 'skip'
  if (state.isProgressiveSwCached) return 'skip'
  return 'progressive_sw'
}

export function consumePrefetchedStream(
  ref: { current: Map<number, PrefetchedStreamRecord> },
  trackId: number,
  nowProvider: () => number = () => Date.now(),
): StreamResponse | null {
  const entry = ref.current.get(trackId)
  if (!entry) return null
  ref.current.delete(trackId)
  const now = nowProvider()
  if (
    entry.expiresAt !== null &&
    entry.expiresAt <= now + 5_000
  ) {
    return null
  }
  return {
    track_id: trackId,
    url: entry.url,
    stream_type: entry.streamType,
    expires_in:
      entry.expiresAt === null
        ? 86_400
        : Math.max(
            1,
            Math.round((entry.expiresAt - now) / 1000),
          ),
  }
}

export function tweenVolume(
  audio: HTMLAudioElement,
  target: number,
  durationMs: number,
): Promise<void> {
  return new Promise((resolve) => {
    const clampedTarget = Math.max(0, Math.min(1, target))
    if (durationMs <= 0) {
      try {
        audio.volume = clampedTarget
      } catch {
        /* ignore */
      }
      resolve()
      return
    }
    const fromVolume = Number.isFinite(audio.volume)
      ? audio.volume
      : clampedTarget
    const startedAt =
      typeof performance !== 'undefined'
        ? performance.now()
        : Date.now()
    const tick = () => {
      const now =
        typeof performance !== 'undefined'
          ? performance.now()
          : Date.now()
      const t = Math.min(1, (now - startedAt) / durationMs)
      const eased = 1 - (1 - t) * (1 - t)
      const v = fromVolume + (clampedTarget - fromVolume) * eased
      try {
        audio.volume = Math.max(0, Math.min(1, v))
      } catch {
        resolve()
        return
      }
      if (t < 1) {
        if (typeof requestAnimationFrame === 'function') {
          requestAnimationFrame(tick)
        } else {
          setTimeout(tick, 16)
        }
      } else {
        resolve()
      }
    }
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(tick)
    } else {
      setTimeout(tick, 16)
    }
  })
}
