import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

type SoundId =
  | 'notificationSuccess'
  | 'notificationWarning'
  | 'notificationError'
  | 'notificationInfo'
  | 'tapSoft'

interface SoundConfig {
  src: string
  volume: number
}

interface SoundContextValue {
  enabled: boolean
  volume: number
  play: (id: SoundId) => void
  setEnabled: (value: boolean) => void
  setVolume: (value: number) => void
}

const DEFAULT_ENABLED = true
const DEFAULT_VOLUME = 0.25

const STORAGE_ENABLED_KEY = 'setting-sound-enabled'
const STORAGE_VOLUME_KEY = 'setting-sound-volume'

const SOUND_MAP: Record<SoundId, SoundConfig> = {
  notificationSuccess: {
    src: '/sounds/notify-success.wav',
    volume: 0.28,
  },
  notificationWarning: {
    src: '/sounds/notify-warning.wav',
    volume: 0.28,
  },
  notificationError: {
    src: '/sounds/notify-error.wav',
    volume: 0.3,
  },
  notificationInfo: {
    src: '/sounds/notify-info.wav',
    volume: 0.24,
  },
  tapSoft: {
    src: '/sounds/tap-soft.wav',
    volume: 0.2,
  },
}

const SoundCtx = createContext<SoundContextValue | null>(
  null,
)

function loadInitialEnabled(): boolean {
  try {
    const stored = localStorage.getItem(
      STORAGE_ENABLED_KEY,
    )
    if (stored === null) return DEFAULT_ENABLED
    return stored === 'true'
  } catch {
    return DEFAULT_ENABLED
  }
}

function loadInitialVolume(): number {
  try {
    const stored = localStorage.getItem(
      STORAGE_VOLUME_KEY,
    )
    if (!stored) return DEFAULT_VOLUME
    const parsed = parseFloat(stored)
    if (!Number.isFinite(parsed)) {
      return DEFAULT_VOLUME
    }
    return Math.max(0, Math.min(1, parsed))
  } catch {
    return DEFAULT_VOLUME
  }
}

export function SoundProvider({
  children,
}: {
  children: ReactNode
}) {
  const [enabled, setEnabledState] = useState(
    () => loadInitialEnabled(),
  )
  const [volume, setVolumeState] = useState(
    () => loadInitialVolume(),
  )
  const audioCacheRef = useRef<Map<SoundId, HTMLAudioElement>>(
    new Map(),
  )
  const userInteractedRef = useRef(false)

  useEffect(() => {
    const handler = () => {
      userInteractedRef.current = true
      window.removeEventListener(
        'pointerdown',
        handler,
      )
      window.removeEventListener('keydown', handler)
    }
    window.addEventListener('pointerdown', handler)
    window.addEventListener('keydown', handler)
    return () => {
      window.removeEventListener(
        'pointerdown',
        handler,
      )
      window.removeEventListener('keydown', handler)
    }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_ENABLED_KEY,
        String(enabled),
      )
    } catch {
      /* ignore */
    }
  }, [enabled])

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_VOLUME_KEY,
        String(volume),
      )
    } catch {
      /* ignore */
    }
  }, [volume])

  const play = useCallback(
    (id: SoundId) => {
      if (!enabled) return
      if (!userInteractedRef.current) return
      const cfg = SOUND_MAP[id]
      if (!cfg) return
      let audio = audioCacheRef.current.get(id)
      if (!audio) {
        try {
          audio = new Audio()
          audio.preload = 'auto'
          audio.src = cfg.src
          audioCacheRef.current.set(id, audio)
        } catch {
          return
        }
      }
      try {
        const base = Math.max(0, Math.min(1, cfg.volume))
        const v = Math.max(
          0,
          Math.min(1, base * volume),
        )
        audio.currentTime = 0
        audio.volume = v
        const p = audio.play()
        if (p && typeof p.catch === 'function') {
          p.catch(() => {})
        }
      } catch {
        /* ignore */
      }
    },
    [enabled, volume],
  )

  const setEnabled = useCallback((value: boolean) => {
    setEnabledState(value)
  }, [])

  const setVolume = useCallback((value: number) => {
    const next = Math.max(0, Math.min(1, value))
    setVolumeState(next)
  }, [])

  const value = useMemo<SoundContextValue>(
    () => ({
      enabled,
      volume,
      play,
      setEnabled,
      setVolume,
    }),
    [enabled, volume, play, setEnabled, setVolume],
  )

  return (
    <SoundCtx.Provider value={value}>
      {children}
    </SoundCtx.Provider>
  )
}

export function useSound(): SoundContextValue {
  const ctx = useContext(SoundCtx)
  if (!ctx) {
    return {
      enabled: false,
      volume: DEFAULT_VOLUME,
      play: () => undefined,
      setEnabled: () => undefined,
      setVolume: () => undefined,
    }
  }
  return ctx
}

