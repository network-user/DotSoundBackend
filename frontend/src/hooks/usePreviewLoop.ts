import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import type { Track } from '@/types/api'

const SILENT_WAV =
  'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA'
const WINDOW_MS = 15000
const SEEK_FRACTION_MIN = 0.2
const SEEK_FRACTION_RANGE = 0.5

interface Opts<K extends string | number> {
  fetcher: (key: K) => Promise<Track[]>
}

export interface UsePreviewLoop<K extends string | number> {
  audioRef: React.RefObject<HTMLAudioElement>
  playingKey: K | null
  loadingKey: K | null
  prime: () => void
  start: (key: K) => Promise<void>
  stop: () => void
}

function shuffle<T>(arr: T[]): T[] {
  const a = arr.slice()
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export function usePreviewLoop<K extends string | number>({
  fetcher,
}: Opts<K>): UsePreviewLoop<K> {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const playingKeyRef = useRef<K | null>(null)
  const timerRef = useRef<number | null>(null)
  const queuesRef = useRef(new Map<K, Track[]>())
  const idxRef = useRef(new Map<K, number>())
  const playNextRef = useRef<((key: K) => void) | null>(null)
  const [playingKey, setPlayingKey] = useState<K | null>(null)
  const [loadingKey, setLoadingKey] = useState<K | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    clearTimer()
    const a = audioRef.current
    if (a) {
      try {
        a.pause()
        a.onended = null
        a.src = ''
      } catch {
        /* ignore */
      }
    }
    playingKeyRef.current = null
    setPlayingKey(null)
    setLoadingKey(null)
  }, [clearTimer])

  const playAt = useCallback(
    (key: K, track: Track) => {
      const a = audioRef.current
      if (!a) return
      clearTimer()
      a.pause()
      a.muted = false
      a.src = `/api/v1/tracks/${track.id}/audio?force_progressive=true`
      try {
        a.load()
      } catch {
        /* ignore */
      }
      const setRandomStart = () => {
        const dur = a.duration
        if (Number.isFinite(dur) && dur > 0) {
          const frac =
            SEEK_FRACTION_MIN +
            Math.random() * SEEK_FRACTION_RANGE
          try {
            a.currentTime = Math.max(0, dur * frac)
          } catch {
            /* ignore */
          }
        }
      }
      const onLoaded = () => {
        a.removeEventListener('loadedmetadata', onLoaded)
        if (playingKeyRef.current !== key) return
        setRandomStart()
      }
      a.addEventListener('loadedmetadata', onLoaded)
      const advance = () => {
        if (playingKeyRef.current !== key) return
        playNextRef.current?.(key)
      }
      a.onended = advance
      setLoadingKey(key)
      const p = a.play()
      if (p && typeof p.then === 'function') {
        p.then(() => {
          if (playingKeyRef.current !== key) return
          setLoadingKey(null)
          setPlayingKey(key)
          clearTimer()
          timerRef.current = window.setTimeout(advance, WINDOW_MS)
        }).catch(() => {
          if (playingKeyRef.current === key) stop()
        })
      }
    },
    [clearTimer, stop],
  )

  const playNext = useCallback(
    (key: K) => {
      if (playingKeyRef.current !== key) return
      const queue = queuesRef.current.get(key)
      if (!queue || queue.length === 0) return
      let idx = idxRef.current.get(key) ?? 0
      if (idx >= queue.length) {
        queuesRef.current.set(key, shuffle(queue))
        idx = 0
      }
      idxRef.current.set(key, idx + 1)
      const track = (queuesRef.current.get(key) ?? queue)[idx]
      if (!track) {
        stop()
        return
      }
      playAt(key, track)
    },
    [playAt, stop],
  )

  playNextRef.current = playNext

  const prime = useCallback(() => {
    const a = audioRef.current
    if (!a) return
    try {
      a.pause()
      a.muted = true
      a.src = SILENT_WAV
      void a.play().catch(() => {})
    } catch {
      /* ignore */
    }
  }, [])

  const start = useCallback(
    async (key: K) => {
      stop()
      playingKeyRef.current = key
      setLoadingKey(key)
      setPlayingKey(null)
      const a = audioRef.current
      if (!a) return
      a.muted = true
      a.src = SILENT_WAV
      try {
        a.load()
      } catch {
        /* ignore */
      }
      void a.play().catch(() => {})

      let queue = queuesRef.current.get(key)
      if (!queue) {
        try {
          const items = await fetcher(key)
          if (playingKeyRef.current !== key) return
          queue = shuffle(items)
          queuesRef.current.set(key, queue)
          idxRef.current.set(key, 0)
        } catch {
          if (playingKeyRef.current === key) stop()
          return
        }
      }
      if (!queue || queue.length === 0) {
        stop()
        return
      }
      if (playingKeyRef.current !== key) return
      playNextRef.current?.(key)
    },
    [fetcher, stop],
  )

  useEffect(() => {
    return () => {
      clearTimer()
      const a = audioRef.current
      if (a) {
        try {
          a.pause()
          a.src = ''
        } catch {
          /* ignore */
        }
      }
    }
  }, [clearTimer])

  return {
    audioRef,
    playingKey,
    loadingKey,
    prime,
    start,
    stop,
  }
}
