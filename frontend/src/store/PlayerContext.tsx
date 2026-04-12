import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import Hls from 'hls.js'
import { api } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import type { Track } from '@/types/api'

const EQ_FREQUENCIES = [
  32, 64, 125, 250, 500, 1000, 4000, 16000,
]
const EQ_DEFAULT = [0, 0, 0, 0, 0, 0, 0, 0]

function _dbToLinear(db: number) {
  return 10 ** (db / 20)
}

function _computeEqHeadroom(
  bands: number[],
) {
  const positive = bands.filter((v) => v > 0)
  const maxBoost =
    positive.length > 0
      ? Math.max(...positive)
      : 0
  const totalBoost = positive.reduce(
    (sum, value) => sum + value,
    0,
  )
  return Math.min(
    9,
    Math.max(maxBoost * 0.75, totalBoost / 3),
  )
}

function _loadEqState() {
  try {
    const rawBands = localStorage.getItem(
      'player-eq-bands',
    )
    const rawPreset = localStorage.getItem(
      'player-eq-preset',
    )
    const rawBypassed = localStorage.getItem(
      'player-eq-bypassed',
    )
    const bands = rawBands
      ? (JSON.parse(rawBands) as number[])
      : EQ_DEFAULT
    return {
      bands:
        Array.isArray(bands) &&
        bands.length === EQ_DEFAULT.length
          ? bands
          : EQ_DEFAULT,
      preset: rawPreset || 'Flat',
      bypassed: rawBypassed === 'true',
    }
  } catch {
    return {
      bands: EQ_DEFAULT,
      preset: 'Flat',
      bypassed: false,
    }
  }
}

function _saveEqState(
  bands: number[],
  preset: string | null,
  bypassed: boolean,
) {
  localStorage.setItem(
    'player-eq-bands',
    JSON.stringify(bands),
  )
  localStorage.setItem(
    'player-eq-preset',
    preset || 'Flat',
  )
  localStorage.setItem(
    'player-eq-bypassed',
    String(bypassed),
  )
}

interface PlayerContextValue {
  track: Track | null
  isPlaying: boolean
  currentTime: number
  duration: number
  volume: number
  setVolume: (v: number) => void
  isComplaintOpen: boolean
  isCardOpen: boolean
  isLyricsOpen: boolean
  isEqOpen: boolean
  eqBands: number[]
  eqPreset: string | null
  eqBypassed: boolean
  playTrack: (
    t: Track,
    url?: string,
  ) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  playNext: () => Promise<void>
  playPrev: () => Promise<void>
  setEqBand: (idx: number, gain: number) => void
  setEqPreset: (preset: string | null) => void
  toggleEqBypass: () => void
  resetEq: () => void
  openComplaint: () => void
  closeComplaint: () => void
  openCard: () => void
  closeCard: () => void
  openLyrics: () => void
  closeLyrics: () => void
  openEq: () => void
  closeEq: () => void
  stop: () => void
}

const PlayerContext =
  createContext<PlayerContextValue | null>(null)

const _SAVE_INTERVAL = 5000

function _saveState(t: Track | null, s: number) {
  if (!t) return
  localStorage.setItem(
    'player-track',
    JSON.stringify(t),
  )
  localStorage.setItem('player-time', String(s))
}

function _loadState() {
  try {
    const r = localStorage.getItem('player-track')
    if (!r) return { track: null, time: 0 }
    return {
      track: JSON.parse(r) as Track,
      time: parseFloat(
        localStorage.getItem('player-time') ||
          '0',
      ),
    }
  } catch {
    return { track: null, time: 0 }
  }
}

function _clearState() {
  localStorage.removeItem('player-track')
  localStorage.removeItem('player-time')
}

function _updateMediaSession(
  track: Track,
  audio: HTMLAudioElement,
  onNext: () => void,
  onPrev: () => void,
) {
  if (!('mediaSession' in navigator)) return
  try {
    navigator.mediaSession.metadata =
      new MediaMetadata({
        title: track.title,
        artist: track.artist || '',
        artwork: track.cover_key
          ? [
              {
                src: `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`,
                sizes: '512x512',
                type: 'image/png',
              },
            ]
          : [],
      })
    navigator.mediaSession.setActionHandler(
      'play',
      () => audio.play(),
    )
    navigator.mediaSession.setActionHandler(
      'pause',
      () => audio.pause(),
    )
    navigator.mediaSession.setActionHandler(
      'nexttrack',
      onNext,
    )
    navigator.mediaSession.setActionHandler(
      'previoustrack',
      onPrev,
    )
    navigator.mediaSession.setActionHandler(
      'seekto',
      (d) => {
        if (
          d.seekTime !== undefined &&
          audio.duration
        )
          audio.currentTime = d.seekTime
      },
    )
  } catch {}
}

function _updatePositionState(
  a: HTMLAudioElement,
) {
  if (
    !('mediaSession' in navigator) ||
    !a.duration
  )
    return
  try {
    navigator.mediaSession.setPositionState({
      duration: a.duration,
      playbackRate: a.playbackRate,
      position: a.currentTime,
    })
  } catch {}
}

export function PlayerProvider({
  children,
}: {
  children: ReactNode
}) {
  const initialEqRef = useRef(_loadEqState())
  const audioRef = useRef<HTMLAudioElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const audioCtxRef =
    useRef<AudioContext | null>(null)
  const filtersRef = useRef<BiquadFilterNode[]>([])
  const eqBandsRef = useRef<number[]>(
    initialEqRef.current.bands,
  )
  const eqBypassedRef = useRef(
    initialEqRef.current.bypassed,
  )
  const postEqGainRef =
    useRef<GainNode | null>(null)
  const sourceRef =
    useRef<MediaElementAudioSourceNode | null>(
      null,
    )
  const eqLoadPromiseRef = useRef<Promise<void> | null>(
    null,
  )
  const eqLoadedRef = useRef(false)
  const eqSaveTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    )
  const lastEqPayloadRef = useRef(
    JSON.stringify({
      preset: initialEqRef.current.preset,
      bands: initialEqRef.current.bands,
    }),
  )

  const [track, setTrack] = useState<Track | null>(
    () => _loadState().track,
  )
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(() => {
    const s = localStorage.getItem('player-volume')
    return s ? parseFloat(s) : 0.8
  })
  const [isComplaintOpen, setIsComplaintOpen] =
    useState(false)
  const [isCardOpen, setIsCardOpen] = useState(false)
  const [isLyricsOpen, setIsLyricsOpen] =
    useState(false)
  const [isEqOpen, setIsEqOpen] = useState(false)
  const [eqBands, setEqBands] =
    useState<number[]>(
      initialEqRef.current.bands,
    )
  const [eqPreset, setEqPresetState] =
    useState<string | null>(
      initialEqRef.current.preset,
    )
  const [eqBypassed, setEqBypassed] =
    useState(initialEqRef.current.bypassed)

  const playCountSentRef = useRef(false)
  const restoredRef = useRef(false)

  const applyEqBands = useCallback(
    (
      bands: number[] = eqBandsRef.current,
      bypassed: boolean = eqBypassedRef.current,
    ) => {
      for (const [
        index,
        filter,
      ] of filtersRef.current.entries()) {
        filter.gain.value = bypassed
          ? 0
          : bands[index] ?? 0
      }

      const out = postEqGainRef.current
      if (out) {
        const headroomDb = bypassed
          ? 0
          : _computeEqHeadroom(bands)
        out.gain.value = _dbToLinear(-headroomDb)
      }
    },
    [],
  )

  const loadEqSettings = useCallback(
    async (force = false) => {
      const uid = getInternalUserId()
      if (!uid) return

      if (
        !force &&
        eqLoadPromiseRef.current
      ) {
        await eqLoadPromiseRef.current
        return
      }

      if (
        eqLoadedRef.current &&
        !force
      ) {
        return
      }

      const promise = api
        .getEqSettings()
        .then((data) => {
          if (data?.bands?.length !== 8) return
          const nextBands = data.bands.map((value) =>
            Number(value),
          )
          const nextPreset =
            data.preset || 'Flat'
          eqBandsRef.current = nextBands
          lastEqPayloadRef.current = JSON.stringify({
            preset: nextPreset,
            bands: nextBands,
          })
          setEqBands(nextBands)
          setEqPresetState(nextPreset)
        })
        .catch(() => {})
        .finally(() => {
          eqLoadedRef.current = true
          eqLoadPromiseRef.current = null
        })

      eqLoadPromiseRef.current = promise
      await promise
    },
    [],
  )

  const setEqPreset = useCallback(
    (preset: string | null) => {
      setEqPresetState(preset)
    },
    [],
  )

  const toggleEqBypass = useCallback(() => {
    setEqBypassed((prev) => !prev)
  }, [])

  const resetEq = useCallback(() => {
    setEqBands(EQ_DEFAULT)
    setEqPresetState('Flat')
    setEqBypassed(false)
  }, [])

  const _initAudioCtx = useCallback(() => {
    const audio = audioRef.current
    if (!audio || audioCtxRef.current) return
    const ctx = new AudioContext()
    audioCtxRef.current = ctx
    const src = ctx.createMediaElementSource(audio)
    sourceRef.current = src

    const filters = EQ_FREQUENCIES.map((freq) => {
      const f = ctx.createBiquadFilter()
      f.type = 'peaking'
      f.frequency.value = freq
      f.Q.value = 1.4
      f.gain.value = 0
      return f
    })
    filtersRef.current = filters

    const out = ctx.createGain()
    postEqGainRef.current = out

    let prev: AudioNode = src
    for (const f of filters) {
      prev.connect(f)
      prev = f
    }
    prev.connect(out)
    out.connect(ctx.destination)
    applyEqBands()
  }, [applyEqBands])

  const setEqBand = useCallback(
    (idx: number, gain: number) => {
      setEqBands((prev) => {
        const next = [...prev]
        next[idx] = gain
        return next
      })
    },
    [],
  )

  useEffect(() => {
    eqBandsRef.current = eqBands
    eqBypassedRef.current = eqBypassed
    applyEqBands()
    _saveEqState(
      eqBands,
      eqPreset,
      eqBypassed,
    )
  }, [
    applyEqBands,
    eqBands,
    eqPreset,
    eqBypassed,
  ])

  useEffect(() => {
    void loadEqSettings()
  }, [loadEqSettings])

  useEffect(() => {
    if (!isEqOpen) return
    void loadEqSettings(true)
  }, [isEqOpen, loadEqSettings])

  useEffect(() => {
    const uid = getInternalUserId()
    if (!uid || !eqLoadedRef.current) return

    const payload = JSON.stringify({
      preset: eqPreset,
      bands: eqBands,
    })
    if (payload === lastEqPayloadRef.current) {
      return
    }

    if (eqSaveTimerRef.current) {
      clearTimeout(eqSaveTimerRef.current)
    }
    eqSaveTimerRef.current = setTimeout(() => {
      api
        .saveEqSettings({
          preset: eqPreset,
          bands: eqBands,
        })
        .then(() => {
          lastEqPayloadRef.current =
            payload
        })
        .catch(() => {})
    }, 800)

    return () => {
      if (eqSaveTimerRef.current) {
        clearTimeout(eqSaveTimerRef.current)
      }
    }
  }, [eqBands, eqPreset])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || restoredRef.current) return
    restoredRef.current = true
    const saved = _loadState()
    if (saved.track) {
      audio.crossOrigin = 'anonymous'
      audio.src = `/api/v1/tracks/${saved.track.id}/audio`
      audio.volume = volume
      if (saved.time > 0) {
        setCurrentTime(saved.time)
        const onMeta = () => {
          audio.currentTime = saved.time
          audio.removeEventListener(
            'loadedmetadata',
            onMeta,
          )
        }
        audio.addEventListener(
          'loadedmetadata',
          onMeta,
        )
      }
    }
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const onPlay = () => {
      setIsPlaying(true)
      if (audioCtxRef.current?.state === 'suspended')
        audioCtxRef.current.resume()
      if (
        !playCountSentRef.current &&
        track &&
        track.id > 0
      ) {
        playCountSentRef.current = true
        api.postPlay(track.id).catch(() => {})
      }
    }
    const onPause = () => setIsPlaying(false)
    const onEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
      playNext()
    }
    const onTime = () => {
      setCurrentTime(audio.currentTime)
      _updatePositionState(audio)
    }
    const onDur = () =>
      setDuration(audio.duration || 0)

    audio.addEventListener('play', onPlay)
    audio.addEventListener('pause', onPause)
    audio.addEventListener('ended', onEnded)
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener(
      'durationchange',
      onDur,
    )
    return () => {
      audio.removeEventListener('play', onPlay)
      audio.removeEventListener('pause', onPause)
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener(
        'timeupdate',
        onTime,
      )
      audio.removeEventListener(
        'durationchange',
        onDur,
      )
    }
  }, [track])

  useEffect(() => {
    const audio = audioRef.current
    if (audio) audio.volume = volume
    localStorage.setItem(
      'player-volume',
      volume.toString(),
    )
  }, [volume])

  useEffect(() => {
    if (!track) return
    const i = setInterval(() => {
      const a = audioRef.current
      if (a) _saveState(track, a.currentTime)
    }, _SAVE_INTERVAL)
    return () => clearInterval(i)
  }, [track])

  const setVolume = (v: number) =>
    setVolumeState(Math.max(0, Math.min(1, v)))

  const startDirectPlayback = useCallback(
    async (
      audio: HTMLAudioElement,
      url: string,
    ) => {
      audio.crossOrigin = 'anonymous'
      audio.src = url
      audio.volume = volume
      await audio.play()
    },
    [volume],
  )

  const startHlsPlayback = useCallback(
    (
      audio: HTMLAudioElement,
      sourceUrl: string,
      fallbackUrl?: string,
    ) =>
      new Promise<void>((resolve) => {
        const hls = new Hls({
          enableWorker: true,
          startLevel: -1,
        })
        hlsRef.current = hls
        hls.loadSource(sourceUrl)
        hls.attachMedia(audio)
        hls.on(
          Hls.Events.MANIFEST_PARSED,
          () => {
            audio.volume = volume
            audio.play().catch(() => {})
            resolve()
          },
        )
        hls.on(Hls.Events.ERROR, (_e, d) => {
          if (!d.fatal) return
          hls.destroy()
          hlsRef.current = null
          if (fallbackUrl) {
            audio.crossOrigin = 'anonymous'
            audio.src = fallbackUrl
            audio.volume = volume
            audio.play().catch(() => {})
          }
          resolve()
        })
      }),
    [volume],
  )

  const playTrack = async (
    newTrack: Track,
    overrideUrl?: string,
  ) => {
    const audio = audioRef.current
    if (!audio) return
    await loadEqSettings()
    _initAudioCtx()
    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }
    playCountSentRef.current = false
    setTrack(newTrack)
    setCurrentTime(0)
    setDuration(0)
    _saveState(newTrack, 0)

    try {
      audio.crossOrigin = 'anonymous'

      if (newTrack.source === 'soundcloud') {
        const stream = await api.getStream(
          newTrack.id,
        )
        if (
          stream.stream_type === 'hls' &&
          Hls.isSupported()
        ) {
          await startHlsPlayback(
            audio,
            stream.url,
          )
        } else {
          await startDirectPlayback(
            audio,
            stream.url,
          )
        }

        _updateMediaSession(
          newTrack,
          audio,
          () => playNext(),
          () => playPrev(),
        )
        return
      }

      const hlsUrl = `/api/v1/tracks/${newTrack.id}/hls/master.m3u8`
      const fallback =
        overrideUrl ||
        `/api/v1/tracks/${newTrack.id}/audio`

      if (Hls.isSupported()) {
        await startHlsPlayback(
          audio,
          hlsUrl,
          fallback,
        )
      } else {
        await startDirectPlayback(
          audio,
          fallback,
        )
      }

      _updateMediaSession(
        newTrack,
        audio,
        () => playNext(),
        () => playPrev(),
      )
    } catch (e) {
      console.error('playTrack error', e)
    }
  }

  const playNext = async () => {
    if (!track) return
    try {
      const adj = await api.getAdjacentTracks(
        track.id,
      )
      if (adj.next_id) {
        const t = await api.getTrack(adj.next_id)
        await playTrack(t)
      }
    } catch {}
  }

  const playPrev = async () => {
    if (!track) return
    const a = audioRef.current
    if (a && a.currentTime > 3) {
      a.currentTime = 0
      return
    }
    try {
      const adj = await api.getAdjacentTracks(
        track.id,
      )
      if (adj.prev_id) {
        const t = await api.getTrack(adj.prev_id)
        await playTrack(t)
      }
    } catch {}
  }

  const togglePlay = async () => {
    const a = audioRef.current
    if (!a || !track) return
    await loadEqSettings()
    _initAudioCtx()
    if (a.paused) a.play()
    else a.pause()
  }

  const seek = (pct: number) => {
    const a = audioRef.current
    if (!a || !a.duration) return
    a.currentTime = (pct / 100) * a.duration
  }

  const stop = () => {
    const a = audioRef.current
    if (a) a.pause()
    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }
    setTrack(null)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
    _clearState()
  }

  return (
    <PlayerContext.Provider
      value={{
        track,
        isPlaying,
        currentTime,
        duration,
        volume,
        setVolume,
        isComplaintOpen,
        isCardOpen,
        isLyricsOpen,
        isEqOpen,
        eqBands,
        eqPreset,
        eqBypassed,
        playTrack,
        togglePlay,
        seek,
        playNext,
        playPrev,
        setEqBand,
        setEqPreset,
        toggleEqBypass,
        resetEq,
        openComplaint: () =>
          setIsComplaintOpen(true),
        closeComplaint: () =>
          setIsComplaintOpen(false),
        openCard: () => setIsCardOpen(true),
        closeCard: () => setIsCardOpen(false),
        openLyrics: () => setIsLyricsOpen(true),
        closeLyrics: () => setIsLyricsOpen(false),
        openEq: () => setIsEqOpen(true),
        closeEq: () => setIsEqOpen(false),
        stop,
      }}
    >
      <audio ref={audioRef} preload="none" />
      {children}
    </PlayerContext.Provider>
  )
}

export function usePlayer() {
  const ctx = useContext(PlayerContext)
  if (!ctx)
    throw new Error(
      'usePlayer must be used within PlayerProvider',
    )
  return ctx
}
