import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import Hls from 'hls.js'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

interface PlayerContextValue {
  track: Track | null
  isPlaying: boolean
  currentTime: number
  duration: number
  volume: number
  setVolume: (volume: number) => void
  isComplaintOpen: boolean
  isCardOpen: boolean
  playTrack: (
    track: Track,
    overrideUrl?: string,
  ) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  playNext: () => Promise<void>
  playPrev: () => Promise<void>
  openComplaint: () => void
  closeComplaint: () => void
  openCard: () => void
  closeCard: () => void
  stop: () => void
}

const PlayerContext =
  createContext<PlayerContextValue | null>(null)

const _SAVE_INTERVAL = 5000

function _saveState(
  track: Track | null,
  time: number,
) {
  if (track) {
    localStorage.setItem(
      'player-track',
      JSON.stringify(track),
    )
    localStorage.setItem(
      'player-time',
      String(time),
    )
  }
}

function _loadState(): {
  track: Track | null
  time: number
} {
  try {
    const raw = localStorage.getItem(
      'player-track',
    )
    if (!raw) return { track: null, time: 0 }
    const track = JSON.parse(raw) as Track
    const time = parseFloat(
      localStorage.getItem('player-time') || '0',
    )
    return { track, time }
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
      (details) => {
        if (
          details.seekTime !== undefined &&
          audio.duration
        ) {
          audio.currentTime = details.seekTime
        }
      },
    )
  } catch {}
}

function _updatePositionState(
  audio: HTMLAudioElement,
) {
  if (
    !('mediaSession' in navigator) ||
    !audio.duration
  )
    return
  try {
    navigator.mediaSession.setPositionState({
      duration: audio.duration,
      playbackRate: audio.playbackRate,
      position: audio.currentTime,
    })
  } catch {}
}

export function PlayerProvider({
  children,
}: {
  children: ReactNode
}) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const hlsRef = useRef<Hls | null>(null)

  const [track, setTrack] = useState<Track | null>(
    () => _loadState().track,
  )
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(() => {
    const saved = localStorage.getItem(
      'player-volume',
    )
    return saved ? parseFloat(saved) : 0.8
  })
  const [isComplaintOpen, setIsComplaintOpen] =
    useState(false)
  const [isCardOpen, setIsCardOpen] = useState(false)
  const playCountSentRef = useRef(false)
  const restoredRef = useRef(false)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    if (restoredRef.current) return
    restoredRef.current = true

    const saved = _loadState()
    if (saved.track) {
      const url = `/api/v1/tracks/${saved.track.id}/audio`
      audio.src = url
      audio.currentTime = saved.time
      audio.volume = volume
    }
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onPlay = () => {
      setIsPlaying(true)
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
    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
      _updatePositionState(audio)
    }
    const onDurationChange = () =>
      setDuration(audio.duration || 0)

    audio.addEventListener('play', onPlay)
    audio.addEventListener('pause', onPause)
    audio.addEventListener('ended', onEnded)
    audio.addEventListener(
      'timeupdate',
      onTimeUpdate,
    )
    audio.addEventListener(
      'durationchange',
      onDurationChange,
    )

    return () => {
      audio.removeEventListener('play', onPlay)
      audio.removeEventListener('pause', onPause)
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener(
        'timeupdate',
        onTimeUpdate,
      )
      audio.removeEventListener(
        'durationchange',
        onDurationChange,
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
    const interval = setInterval(() => {
      const audio = audioRef.current
      if (audio) {
        _saveState(track, audio.currentTime)
      }
    }, _SAVE_INTERVAL)
    return () => clearInterval(interval)
  }, [track])

  const setVolume = (v: number) => {
    setVolumeState(Math.max(0, Math.min(1, v)))
  }

  const playTrack = async (
    newTrack: Track,
    overrideUrl?: string,
  ) => {
    const audio = audioRef.current
    if (!audio) return

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
      const hlsUrl = `/api/v1/tracks/${newTrack.id}/hls/master.m3u8`
      const fallbackUrl =
        overrideUrl ||
        `/api/v1/tracks/${newTrack.id}/audio`

      if (Hls.isSupported()) {
        const hls = new Hls({
          enableWorker: true,
          startLevel: -1,
        })
        hlsRef.current = hls
        hls.loadSource(hlsUrl)
        hls.attachMedia(audio)
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          audio.volume = volume
          audio.play().catch(() => {})
        })
        hls.on(
          Hls.Events.ERROR,
          (_event, data) => {
            if (data.fatal) {
              hls.destroy()
              hlsRef.current = null
              audio.src = fallbackUrl
              audio.volume = volume
              audio.play().catch(() => {})
            }
          },
        )
      } else {
        audio.src = fallbackUrl
        audio.volume = volume
        await audio.play()
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
        const nextTrack = await api.getTrack(
          adj.next_id,
        )
        await playTrack(nextTrack)
      }
    } catch {}
  }

  const playPrev = async () => {
    if (!track) return
    const audio = audioRef.current
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0
      return
    }
    try {
      const adj = await api.getAdjacentTracks(
        track.id,
      )
      if (adj.prev_id) {
        const prevTrack = await api.getTrack(
          adj.prev_id,
        )
        await playTrack(prevTrack)
      }
    } catch {}
  }

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio || !track) return
    if (audio.paused) audio.play()
    else audio.pause()
  }

  const seek = (pct: number) => {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    audio.currentTime =
      (pct / 100) * audio.duration
  }

  const stop = () => {
    const audio = audioRef.current
    if (audio) audio.pause()
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
        playTrack,
        togglePlay,
        seek,
        playNext,
        playPrev,
        openComplaint: () =>
          setIsComplaintOpen(true),
        closeComplaint: () =>
          setIsComplaintOpen(false),
        openCard: () => setIsCardOpen(true),
        closeCard: () => setIsCardOpen(false),
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
