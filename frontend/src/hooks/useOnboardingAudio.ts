import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { trackActivationEvent } from '@/lib/activation'

export type OnboardingAudioState =
  | 'idle'
  | 'loading'
  | 'playing'
  | 'paused'
  | 'blocked'
  | 'error'

export type OnboardingAudioErrCode =
  | 'autoplay_blocked'
  | 'aborted'
  | 'network'
  | 'unknown'

const SILENT_WAV =
  'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA'

interface PlayMeta {
  step?: string
}

export interface UseOnboardingAudio {
  audioRef: React.RefObject<HTMLAudioElement>
  state: OnboardingAudioState
  lastError: OnboardingAudioErrCode | null
  currentTrackId: number | null
  prime: () => void
  playTrack: (
    id: number,
    src: string,
    meta?: PlayMeta,
  ) => void
  toggle: (meta?: PlayMeta) => void
  stop: () => void
}

function classifyError(
  e: unknown,
): OnboardingAudioErrCode {
  if (e && typeof e === 'object' && 'name' in e) {
    const n = (e as { name: string }).name
    if (n === 'NotAllowedError')
      return 'autoplay_blocked'
    if (n === 'AbortError') return 'aborted'
    if (n === 'NotSupportedError') return 'network'
  }
  return 'unknown'
}

export function useOnboardingAudio(): UseOnboardingAudio {
  const audioRef = useRef<HTMLAudioElement>(null)
  const tokenRef = useRef(0)
  const trackIdRef = useRef<number | null>(null)
  const [state, setState] =
    useState<OnboardingAudioState>('idle')
  const [lastError, setLastError] =
    useState<OnboardingAudioErrCode | null>(null)
  const [currentTrackId, setCurrentTrackId] = useState<
    number | null
  >(null)

  const reportSilent = useCallback(
    (
      code: OnboardingAudioErrCode,
      meta: PlayMeta | undefined,
    ) => {
      trackActivationEvent('audio_silent', {
        meta: {
          step: meta?.step ?? 'unknown',
          code,
        },
      })
    },
    [],
  )

  const prime = useCallback(() => {
    const a = audioRef.current
    if (!a) return
    // iOS/Telegram WebView only allows .play() inside a
    // user gesture. Calling muted+silent here unlocks
    // the element for the next async playback attempt.
    try {
      a.pause()
      a.muted = true
      a.src = SILENT_WAV
      void a.play().catch(() => {})
    } catch {
      /* ignore */
    }
  }, [])

  const playTrack = useCallback(
    (id: number, src: string, meta?: PlayMeta) => {
      const a = audioRef.current
      if (!a) return
      tokenRef.current += 1
      const token = tokenRef.current
      trackIdRef.current = id
      setCurrentTrackId(id)
      setLastError(null)
      try {
        a.pause()
        a.muted = false
        a.src = src
        a.load()
      } catch {
        /* ignore */
      }
      setState('loading')
      const p = a.play()
      if (!p) return
      p.then(() => {
        if (tokenRef.current !== token) return
        setState('playing')
      }).catch((e: unknown) => {
        if (tokenRef.current !== token) return
        const code = classifyError(e)
        if (code === 'aborted') return
        setLastError(code)
        setState(
          code === 'autoplay_blocked'
            ? 'blocked'
            : 'error',
        )
        reportSilent(code, meta)
      })
    },
    [reportSilent],
  )

  const toggle = useCallback(
    (meta?: PlayMeta) => {
      const a = audioRef.current
      if (!a) return
      if (a.paused) {
        tokenRef.current += 1
        const token = tokenRef.current
        a.muted = false
        const p = a.play()
        if (!p) return
        p.then(() => {
          if (tokenRef.current !== token) return
          setState('playing')
          setLastError(null)
        }).catch((e: unknown) => {
          if (tokenRef.current !== token) return
          const code = classifyError(e)
          if (code === 'aborted') return
          setLastError(code)
          setState(
            code === 'autoplay_blocked'
              ? 'blocked'
              : 'error',
          )
          reportSilent(code, meta)
        })
      } else {
        a.pause()
        setState('paused')
      }
    },
    [reportSilent],
  )

  const stop = useCallback(() => {
    const a = audioRef.current
    tokenRef.current += 1
    if (a) {
      try {
        a.pause()
        a.src = ''
      } catch {
        /* ignore */
      }
    }
    trackIdRef.current = null
    setCurrentTrackId(null)
    setState('idle')
  }, [])

  useEffect(() => {
    const a = audioRef.current
    if (!a) return
    const onPause = () => {
      if (a.ended) return
      setState((prev) =>
        prev === 'playing' ? 'paused' : prev,
      )
    }
    const onEnded = () => {
      setState('paused')
    }
    const onError = () => {
      setLastError('network')
      setState('error')
    }
    a.addEventListener('pause', onPause)
    a.addEventListener('ended', onEnded)
    a.addEventListener('error', onError)
    return () => {
      a.removeEventListener('pause', onPause)
      a.removeEventListener('ended', onEnded)
      a.removeEventListener('error', onError)
    }
  }, [])

  useEffect(() => {
    return () => {
      const a = audioRef.current
      tokenRef.current += 1
      if (a) {
        try {
          a.pause()
          a.src = ''
        } catch {
          /* ignore */
        }
      }
    }
  }, [])

  return {
    audioRef,
    state,
    lastError,
    currentTrackId,
    prime,
    playTrack,
    toggle,
    stop,
  }
}
