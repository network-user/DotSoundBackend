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
import Hls from 'hls.js'
import { api } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { useToast } from '@/components/ui/Toast'
import { getCachedAudioUrl } from '@/lib/offlineCache'
import { queueOrSend } from '@/lib/pendingEvents'
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
  isQueueOpen: boolean
  eqBands: number[]
  eqPreset: string | null
  eqBypassed: boolean
  repeatMode: 'none' | 'one' | 'all'
  shuffleOn: boolean
  hlsError: string | null
  playbackRate: number
  queue: Track[]
  history: Track[]
  abLoop: { a: number | null; b: number | null }
  toggleRepeat: () => void
  toggleShuffle: () => void
  clearHlsError: () => void
  playTrack: (
    t: Track,
    url?: string,
  ) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  seekToSeconds: (sec: number) => void
  skipForward: (s?: number) => void
  skipBackward: (s?: number) => void
  setPlaybackRate: (rate: number) => void
  playNext: () => Promise<boolean>
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
  openQueue: () => void
  closeQueue: () => void
  addToQueue: (t: Track) => void
  removeFromQueue: (idx: number) => void
  clearQueue: () => void
  reorderQueue: (from: number, to: number) => void
  setAbA: (sec?: number) => void
  setAbB: (sec?: number) => void
  clearAbLoop: () => void
  stop: () => void
  getAnalyser: () => AnalyserNode | null
  updateTrack: (updated: Partial<Track> & { id: number }) => void
}

interface PlayerStateValue {
  currentTime: number
  duration: number
  isPlaying: boolean
}

interface PlayerActionsValue {
  playTrack: (t: Track, url?: string) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  seekToSeconds: (sec: number) => void
  skipForward: (s?: number) => void
  skipBackward: (s?: number) => void
  setPlaybackRate: (rate: number) => void
  playNext: () => Promise<boolean>
  playPrev: () => Promise<void>
  setVolume: (v: number) => void
  stop: () => void
  setEqBand: (idx: number, gain: number) => void
  setEqPreset: (preset: string | null) => void
  toggleEqBypass: () => void
  resetEq: () => void
  toggleRepeat: () => void
  toggleShuffle: () => void
  clearHlsError: () => void
  openComplaint: () => void
  closeComplaint: () => void
  openCard: () => void
  closeCard: () => void
  openLyrics: () => void
  closeLyrics: () => void
  openEq: () => void
  closeEq: () => void
  openQueue: () => void
  closeQueue: () => void
  addToQueue: (t: Track) => void
  removeFromQueue: (idx: number) => void
  clearQueue: () => void
  reorderQueue: (from: number, to: number) => void
  setAbA: (sec?: number) => void
  setAbB: (sec?: number) => void
  clearAbLoop: () => void
  getAnalyser: () => AnalyserNode | null
  updateTrack: (updated: Partial<Track> & { id: number }) => void
}

interface PlayerMetaValue {
  track: Track | null
  volume: number
  isComplaintOpen: boolean
  isCardOpen: boolean
  isLyricsOpen: boolean
  isEqOpen: boolean
  isQueueOpen: boolean
  eqBands: number[]
  eqPreset: string | null
  eqBypassed: boolean
  repeatMode: 'none' | 'one' | 'all'
  shuffleOn: boolean
  hlsError: string | null
  playbackRate: number
  queue: Track[]
  history: Track[]
  abLoop: { a: number | null; b: number | null }
}

const PlayerStateCtx = createContext<PlayerStateValue | null>(null)
const PlayerActionsCtx = createContext<PlayerActionsValue | null>(null)
const PlayerMetaCtx = createContext<PlayerMetaValue | null>(null)

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
    const coverPath = track.cover_key
      ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
      : null
    const coverAbsolute = coverPath
      ? new URL(coverPath, window.location.origin).href
      : null

    navigator.mediaSession.metadata =
      new MediaMetadata({
        title: track.title,
        artist: track.artist || '',
        artwork: coverAbsolute
          ? [
              {
                src: coverAbsolute,
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
  const toast = useToast()
  const initialEqRef = useRef(_loadEqState())
  const audioRef = useRef<HTMLAudioElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const prefetchCacheRef = useRef<{
    forTrackId: number
    tracks: Track[]
  } | null>(null)
  const historyRef = useRef<Track[]>([])
  const prefetchAudioRef =
    useRef<HTMLAudioElement | null>(null)
  const manualQueueRef = useRef<Track[]>([])
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamExpiresAtRef = useRef<number | null>(null)
  const lastStreamUrlRef = useRef<string | null>(null)
  const lastTrackIdRef = useRef<number | null>(null)
  const preloadHlsRef = useRef<Hls | null>(null)
  const preloadHlsTrackIdRef = useRef<number | null>(
    null,
  )
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
  const [isQueueOpen, setIsQueueOpen] = useState(false)
  const [playbackRate, setPlaybackRateState] =
    useState(1)
  const [queue, setQueue] = useState<Track[]>([])
  const [history, setHistory] = useState<Track[]>([])
  const [abLoop, setAbLoop] = useState<{
    a: number | null
    b: number | null
  }>({ a: null, b: null })
  const abLoopRef = useRef<{
    a: number | null
    b: number | null
  }>({ a: null, b: null })
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
  const [repeatMode, setRepeatMode] = useState<'none' | 'one' | 'all'>(
    () => (localStorage.getItem('player-repeat') as 'none' | 'one' | 'all') ?? 'none',
  )
  const [shuffleOn, setShuffleOn] = useState(
    () => localStorage.getItem('player-shuffle') === 'true',
  )
  const [hlsError, setHlsError] = useState<string | null>(null)
  const repeatModeRef = useRef<'none' | 'one' | 'all'>(
    (localStorage.getItem('player-repeat') as 'none' | 'one' | 'all') ?? 'none',
  )
  const shuffleOnRef = useRef(localStorage.getItem('player-shuffle') === 'true')

  const playCountSentRef = useRef(false)
  const listenSignalSentRef = useRef(false)
  const listenStartTimeRef = useRef(0)
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

    const analyser = ctx.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.82
    analyserRef.current = analyser

    let prev: AudioNode = src
    for (const f of filters) {
      prev.connect(f)
      prev = f
    }
    prev.connect(out)
    out.connect(analyser)
    analyser.connect(ctx.destination)
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
      setTrack(saved.track)
      audio.crossOrigin = 'anonymous'
      audio.volume = volume

      const seekAfterLoad = () => {
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

      if (!saved.track.is_public) {
        api.getStream(saved.track.id)
          .then((stream) => {
            audio.src = stream.url
            seekAfterLoad()
          })
          .catch(() => {})
      } else {
        const hlsUrl = `/api/v1/tracks/${saved.track.id}/hls/master.m3u8`
        const fallback = `/api/v1/tracks/${saved.track.id}/audio`

        if (Hls.isSupported()) {
          startHlsPlayback(audio, hlsUrl, fallback, false)
            .then(seekAfterLoad)
            .catch(() => {})
        } else {
          audio.src = fallback
          seekAfterLoad()
        }
      }
    }
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const sendListenSignal = () => {
      if (
        listenSignalSentRef.current ||
        !track ||
        track.id <= 0
      )
        return
      const listened = Math.floor(
        audio.currentTime - listenStartTimeRef.current,
      )
      if (listened <= 0) return
      listenSignalSentRef.current = true
      void queueOrSend(
        'record-listen',
        '/api/v1/signals/listen',
        {
          track_id: track.id,
          duration_listened: listened,
          total_duration: track.duration_seconds,
          source_context: 'player',
        },
      )
    }

    const onPlay = () => {
      setIsPlaying(true)
      if ('mediaSession' in navigator)
        navigator.mediaSession.playbackState = 'playing'
      if (audioCtxRef.current?.state === 'suspended')
        audioCtxRef.current.resume()
      if (
        !playCountSentRef.current &&
        track &&
        track.id > 0
      ) {
        playCountSentRef.current = true
        void queueOrSend(
          'post-play',
          `/api/v1/tracks/${track.id}/play`,
          {},
        )
      }
      listenStartTimeRef.current =
        audio.currentTime
    }
    const onPause = () => {
      setIsPlaying(false)
      if ('mediaSession' in navigator)
        navigator.mediaSession.playbackState = 'paused'
      sendListenSignal()
    }
    const onEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
      sendListenSignal()
      const audio = audioRef.current
      if (repeatModeRef.current === 'one' && audio) {
        audio.currentTime = 0
        audio.play().catch(() => {})
        return
      }
      playNext().then((played) => {
        if (
          !played &&
          repeatModeRef.current === 'all' &&
          audioRef.current &&
          track
        ) {
          audioRef.current.currentTime = 0
          audioRef.current.play().catch(() => {})
        }
      })
    }
    const onError = () => {
      const a = audioRef.current
      if (!a || !track) return
      const code = a.error?.code
      if (
        code === MediaError.MEDIA_ERR_NETWORK ||
        code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED
      ) {
        const expires = streamExpiresAtRef.current
        if (
          expires &&
          Date.now() > expires - 30_000 &&
          !track.is_public
        ) {
          api
            .getStream(track.id)
            .then((stream) => {
              if (a && stream?.url) {
                const t = a.currentTime
                a.src = stream.url
                a.currentTime = t
                a.play().catch(() => {})
                streamExpiresAtRef.current =
                  stream.expires_in
                    ? Date.now() +
                      stream.expires_in * 1000
                    : null
                lastStreamUrlRef.current = stream.url
              }
            })
            .catch(() =>
              toast.error(
                'Не удалось обновить ссылку на трек',
              ),
            )
          return
        }
      }
      toast.error('Ошибка воспроизведения трека')
    }
    const onStalled = () => {
      try {
        toast.warning('Буферизация…', {
          duration: 1800,
        })
      } catch {
        /* ignore */
      }
    }
    const onTime = () => {
      const ab = abLoopRef.current
      if (
        ab.a !== null &&
        ab.b !== null &&
        ab.b > ab.a &&
        audio.currentTime >= ab.b
      ) {
        audio.currentTime = ab.a
      }
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
    audio.addEventListener('error', onError)
    audio.addEventListener('stalled', onStalled)

    if (track) {
      _updateMediaSession(
        track,
        audio,
        () => playNext(),
        () => playPrev(),
      )
    }

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
      audio.removeEventListener('error', onError)
      audio.removeEventListener('stalled', onStalled)
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

  const toggleRepeat = useCallback(() => {
    setRepeatMode((prev) => {
      const next = prev === 'none' ? 'one' : prev === 'one' ? 'all' : 'none'
      repeatModeRef.current = next
      localStorage.setItem('player-repeat', next)
      return next
    })
  }, [])

  const toggleShuffle = useCallback(() => {
    setShuffleOn((prev) => {
      shuffleOnRef.current = !prev
      localStorage.setItem('player-shuffle', String(!prev))
      return !prev
    })
  }, [])

  const clearHlsError = useCallback(() => setHlsError(null), [])

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
      autoplay = true,
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
            if (autoplay) audio.play().catch(() => {})
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
            if (autoplay) audio.play().catch(() => {})
          } else {
            setHlsError('Ошибка воспроизведения')
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
    setTrack((prev) => {
      if (prev && prev.id !== newTrack.id) {
        const h = historyRef.current
        if (
          h.length === 0 ||
          h[h.length - 1].id !== prev.id
        ) {
          h.push(prev)
          if (h.length > 50) h.shift()
          setHistory([...h])
        }
      }
      return newTrack
    })
    streamExpiresAtRef.current = null
    lastStreamUrlRef.current = null
    lastTrackIdRef.current = newTrack.id
    await loadEqSettings()
    _initAudioCtx()
    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }
    playCountSentRef.current = false
    listenSignalSentRef.current = false
    listenStartTimeRef.current = 0
    setCurrentTime(0)
    setDuration(0)
    _saveState(newTrack, 0)
    if (audio) audio.playbackRate = playbackRate

    try {
      audio.crossOrigin = 'anonymous'

      const cachedUrl = await getCachedAudioUrl(
        newTrack.id,
      )
      if (cachedUrl) {
        await startDirectPlayback(audio, cachedUrl)
        _updateMediaSession(
          newTrack,
          audio,
          () => playNext(),
          () => playPrev(),
        )
        return
      }

      if (newTrack.access_mode === 'third_party_stream') {
        const stream = await api.getStream(
          newTrack.id,
        )
        lastStreamUrlRef.current = stream.url
        streamExpiresAtRef.current = stream.expires_in
          ? Date.now() + stream.expires_in * 1000
          : null
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

      if (!newTrack.is_public) {
        const stream = await api.getStream(newTrack.id)
        lastStreamUrlRef.current = stream.url
        streamExpiresAtRef.current = stream.expires_in
          ? Date.now() + stream.expires_in * 1000
          : null
        await startDirectPlayback(audio, stream.url)
        _updateMediaSession(newTrack, audio, () => playNext(), () => playPrev())
        return
      }

      const hlsUrl = `/api/v1/tracks/${newTrack.id}/hls/master.m3u8`
      const fallback =
        overrideUrl ||
        `/api/v1/tracks/${newTrack.id}/audio`

      if (Hls.isSupported()) {
        const preloaded =
          preloadHlsRef.current &&
          preloadHlsTrackIdRef.current ===
            newTrack.id
            ? preloadHlsRef.current
            : null
        if (preloaded) {
          try {
            preloaded.detachMedia()
            preloaded.attachMedia(audio)
            audio.volume = volume
            await audio.play().catch(() => {})
            hlsRef.current = preloaded
            preloadHlsRef.current = null
            preloadHlsTrackIdRef.current = null
          } catch {
            await startHlsPlayback(
              audio,
              hlsUrl,
              fallback,
            )
          }
        } else {
          await startHlsPlayback(
            audio,
            hlsUrl,
            fallback,
          )
        }
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

  const playNext = async (): Promise<boolean> => {
    if (!track) return false
    try {
      if (manualQueueRef.current.length > 0) {
        const next = manualQueueRef.current.shift()!
        setQueue([...manualQueueRef.current])
        await playTrack(next)
        return true
      }
      const cache = prefetchCacheRef.current
      if (
        cache &&
        cache.forTrackId === track.id &&
        cache.tracks.length > 0
      ) {
        let next: Track
        if (shuffleOnRef.current && cache.tracks.length > 1) {
          const idx = Math.floor(Math.random() * cache.tracks.length)
          next = cache.tracks[idx]
          prefetchCacheRef.current = {
            forTrackId: next.id,
            tracks: cache.tracks.filter((_, i) => i !== idx),
          }
        } else {
          next = cache.tracks[0]
          prefetchCacheRef.current = {
            forTrackId: next.id,
            tracks: cache.tracks.slice(1),
          }
        }
        await playTrack(next)
        return true
      }
      const adj = await api.getAdjacentTracks(
        track.id,
      )
      if (adj.next_id) {
        const t = await api.getTrack(adj.next_id)
        await playTrack(t)
        return true
      }
      return false
    } catch {
      return false
    }
  }

  useEffect(() => {
    if (!track) return
    let cancelled = false

    const teardownPreloadHls = () => {
      if (preloadHlsRef.current) {
        try {
          preloadHlsRef.current.destroy()
        } catch {
          /* ignore */
        }
        preloadHlsRef.current = null
      }
      preloadHlsTrackIdRef.current = null
    }

    const preloadFirst = (tracks: Track[]) => {
      if (cancelled || !tracks.length) return
      const next = tracks[0]
      if (prefetchAudioRef.current) {
        prefetchAudioRef.current.src = ''
        prefetchAudioRef.current = null
      }
      teardownPreloadHls()

      const pa = new Audio()
      pa.preload = 'auto'
      pa.src = `/api/v1/tracks/${next.id}/audio`
      prefetchAudioRef.current = pa

      const canHls =
        next.is_public &&
        next.access_mode !== 'third_party_stream' &&
        Hls.isSupported()
      if (!canHls) return

      try {
        const hls = new Hls({
          enableWorker: true,
          startLevel: -1,
          autoStartLoad: true,
          maxBufferLength: 12,
        })
        hls.loadSource(
          `/api/v1/tracks/${next.id}/hls/master.m3u8`,
        )
        const sink = document.createElement('audio')
        sink.muted = true
        sink.preload = 'auto'
        hls.attachMedia(sink)
        preloadHlsRef.current = hls
        preloadHlsTrackIdRef.current = next.id
        hls.on(Hls.Events.ERROR, (_e, d) => {
          if (d.fatal) teardownPreloadHls()
        })
      } catch {
        teardownPreloadHls()
      }
    }

    api.getRadio(track.id, 5)
      .then((res) => {
        if (cancelled || !res.tracks.length)
          throw new Error('empty')
        prefetchCacheRef.current = {
          forTrackId: track.id,
          tracks: res.tracks,
        }
        preloadFirst(res.tracks)
      })
      .catch(() => {
        api.getTrackQueue(track.id, 3)
          .then((res) => {
            if (cancelled) return
            prefetchCacheRef.current = {
              forTrackId: track.id,
              tracks: res.next_tracks,
            }
            preloadFirst(res.next_tracks)
          })
          .catch(() => {})
      })
    return () => {
      cancelled = true
      if (prefetchAudioRef.current) {
        prefetchAudioRef.current.src = ''
        prefetchAudioRef.current = null
      }
      teardownPreloadHls()
    }
  }, [track?.id])

  const playPrev = async () => {
    if (!track) return
    const a = audioRef.current
    if (a && a.currentTime > 3) {
      a.currentTime = 0
      return
    }
    const prev = historyRef.current.pop()
    if (prev) {
      await playTrack(prev)
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
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = null
      navigator.mediaSession.playbackState = 'none'
    }
    setTrack(null)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
    _clearState()
  }

  const seekToSeconds = useCallback((sec: number) => {
    const a = audioRef.current
    if (!a || !a.duration) return
    a.currentTime = Math.max(
      0,
      Math.min(a.duration, sec),
    )
  }, [])

  const skipForward = useCallback((s = 15) => {
    const a = audioRef.current
    if (!a) return
    a.currentTime = Math.min(
      a.duration || 0,
      a.currentTime + s,
    )
  }, [])

  const skipBackward = useCallback((s = 15) => {
    const a = audioRef.current
    if (!a) return
    a.currentTime = Math.max(0, a.currentTime - s)
  }, [])

  const setPlaybackRate = useCallback(
    (rate: number) => {
      const r = Math.max(0.25, Math.min(2, rate))
      setPlaybackRateState(r)
      const a = audioRef.current
      if (a) a.playbackRate = r
    },
    [],
  )

  const addToQueue = useCallback((t: Track) => {
    manualQueueRef.current = [
      ...manualQueueRef.current,
      t,
    ]
    setQueue([...manualQueueRef.current])
  }, [])

  const removeFromQueue = useCallback(
    (idx: number) => {
      manualQueueRef.current =
        manualQueueRef.current.filter(
          (_, i) => i !== idx,
        )
      setQueue([...manualQueueRef.current])
    },
    [],
  )

  const clearQueue = useCallback(() => {
    manualQueueRef.current = []
    setQueue([])
  }, [])

  const reorderQueue = useCallback(
    (from: number, to: number) => {
      const arr = [...manualQueueRef.current]
      if (
        from < 0 ||
        from >= arr.length ||
        to < 0 ||
        to >= arr.length
      )
        return
      const [item] = arr.splice(from, 1)
      arr.splice(to, 0, item)
      manualQueueRef.current = arr
      setQueue(arr)
    },
    [],
  )

  const setAbA = useCallback((sec?: number) => {
    const a = audioRef.current
    const value =
      sec ?? (a ? a.currentTime : 0)
    setAbLoop((prev) => {
      const next = { a: value, b: prev.b }
      abLoopRef.current = next
      return next
    })
  }, [])

  const setAbB = useCallback((sec?: number) => {
    const a = audioRef.current
    const value =
      sec ?? (a ? a.currentTime : 0)
    setAbLoop((prev) => {
      const next = { a: prev.a, b: value }
      abLoopRef.current = next
      return next
    })
  }, [])

  const clearAbLoop = useCallback(() => {
    setAbLoop(() => {
      const next = { a: null, b: null }
      abLoopRef.current = next
      return next
    })
  }, [])

  const getAnalyser = useCallback(
    () => analyserRef.current,
    [],
  )

  const updateTrack = useCallback(
    (updated: Partial<Track> & { id: number }) => {
      setTrack((prev) => {
        if (!prev || prev.id !== updated.id)
          return prev
        const merged = { ...prev, ...updated }
        _saveState(merged, audioRef.current?.currentTime ?? 0)
        return merged
      })
    },
    [],
  )

  const stateValue = useMemo<PlayerStateValue>(
    () => ({ currentTime, duration, isPlaying }),
    [currentTime, duration, isPlaying],
  )

  const openComplaint = useCallback(
    () => setIsComplaintOpen(true), [],
  )
  const closeComplaint = useCallback(
    () => setIsComplaintOpen(false), [],
  )
  const openCard = useCallback(
    () => setIsCardOpen(true), [],
  )
  const closeCard = useCallback(
    () => setIsCardOpen(false), [],
  )
  const openLyrics = useCallback(
    () => setIsLyricsOpen(true), [],
  )
  const closeLyrics = useCallback(
    () => setIsLyricsOpen(false), [],
  )
  const openEq = useCallback(
    () => setIsEqOpen(true), [],
  )
  const closeEq = useCallback(
    () => setIsEqOpen(false), [],
  )
  const openQueue = useCallback(
    () => setIsQueueOpen(true), [],
  )
  const closeQueue = useCallback(
    () => setIsQueueOpen(false), [],
  )

  const actionsValue = useMemo<PlayerActionsValue>(
    () => ({
      playTrack, togglePlay, seek, seekToSeconds,
      skipForward, skipBackward, setPlaybackRate,
      playNext, playPrev, setVolume, stop,
      setEqBand, setEqPreset, toggleEqBypass, resetEq,
      toggleRepeat, toggleShuffle, clearHlsError,
      openComplaint, closeComplaint,
      openCard, closeCard,
      openLyrics, closeLyrics,
      openEq, closeEq,
      openQueue, closeQueue,
      addToQueue, removeFromQueue, clearQueue, reorderQueue,
      setAbA, setAbB, clearAbLoop,
      getAnalyser,
      updateTrack,
    }),
    [
      playTrack, togglePlay, seek, seekToSeconds,
      skipForward, skipBackward, setPlaybackRate,
      playNext, playPrev, setVolume, stop,
      setEqBand, setEqPreset, toggleEqBypass, resetEq,
      toggleRepeat, toggleShuffle, clearHlsError,
      openComplaint, closeComplaint,
      openCard, closeCard,
      openLyrics, closeLyrics,
      openEq, closeEq,
      openQueue, closeQueue,
      addToQueue, removeFromQueue, clearQueue, reorderQueue,
      setAbA, setAbB, clearAbLoop,
      getAnalyser,
      updateTrack,
    ],
  )

  const metaValue = useMemo<PlayerMetaValue>(
    () => ({
      track, volume,
      isComplaintOpen, isCardOpen,
      isLyricsOpen, isEqOpen, isQueueOpen,
      eqBands, eqPreset, eqBypassed,
      repeatMode, shuffleOn, hlsError,
      playbackRate, queue, history,
      abLoop,
    }),
    [
      track, volume,
      isComplaintOpen, isCardOpen,
      isLyricsOpen, isEqOpen, isQueueOpen,
      eqBands, eqPreset, eqBypassed,
      repeatMode, shuffleOn, hlsError,
      playbackRate, queue, history,
      abLoop,
    ],
  )

  const legacyValue = useMemo<PlayerContextValue>(
    () => ({
      ...stateValue,
      ...actionsValue,
      ...metaValue,
    }),
    [stateValue, actionsValue, metaValue],
  )

  return (
    <PlayerContext.Provider value={legacyValue}>
      <PlayerStateCtx.Provider value={stateValue}>
        <PlayerActionsCtx.Provider value={actionsValue}>
          <PlayerMetaCtx.Provider value={metaValue}>
            <audio ref={audioRef} preload="none" />
            {children}
          </PlayerMetaCtx.Provider>
        </PlayerActionsCtx.Provider>
      </PlayerStateCtx.Provider>
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

export function usePlayerState() {
  const ctx = useContext(PlayerStateCtx)
  if (!ctx)
    throw new Error(
      'usePlayerState must be used within PlayerProvider',
    )
  return ctx
}

export function usePlayerActions() {
  const ctx = useContext(PlayerActionsCtx)
  if (!ctx)
    throw new Error(
      'usePlayerActions must be used within PlayerProvider',
    )
  return ctx
}

export function usePlayerMeta() {
  const ctx = useContext(PlayerMetaCtx)
  if (!ctx)
    throw new Error(
      'usePlayerMeta must be used within PlayerProvider',
    )
  return ctx
}
