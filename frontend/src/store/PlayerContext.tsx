import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
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
  openComplaint: () => void
  closeComplaint: () => void
  openCard: () => void
  closeCard: () => void
  stop: () => void
}

const PlayerContext =
  createContext<PlayerContextValue | null>(null)

function updateMediaSession(
  track: Track,
  audio: HTMLAudioElement,
): void {
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

export function PlayerProvider({
  children,
}: {
  children: ReactNode
}) {
  const audioRef = useRef<HTMLAudioElement>(null)

  const [track, setTrack] = useState<Track | null>(
    null,
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
    }
    const onTimeUpdate = () =>
      setCurrentTime(audio.currentTime)
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

  const setVolume = (v: number) => {
    setVolumeState(Math.max(0, Math.min(1, v)))
  }

  const playTrack = async (
    newTrack: Track,
    overrideUrl?: string,
  ) => {
    const audio = audioRef.current
    if (!audio) return
    playCountSentRef.current = false
    setTrack(newTrack)
    setCurrentTime(0)
    setDuration(0)
    try {
      const url =
        overrideUrl ||
        `/api/v1/tracks/${newTrack.id}/audio`
      audio.src = url
      audio.volume = volume
      await audio.play()
      updateMediaSession(newTrack, audio)
    } catch (e) {
      console.error('playTrack error', e)
    }
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
    setTrack(null)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
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
