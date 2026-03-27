import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

interface PlayerContextValue {
  track: Track | null
  isPlaying: boolean
  currentTime: number
  duration: number
  isComplaintOpen: boolean
  playTrack: (track: Track) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  openComplaint: () => void
  closeComplaint: () => void
  stop: () => void
}

const PlayerContext = createContext<PlayerContextValue | null>(null)

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [track, setTrack] = useState<Track | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isComplaintOpen, setIsComplaintOpen] = useState(false)
  const playCountSentRef = useRef(false)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onPlay = () => {
      setIsPlaying(true)
      if (!playCountSentRef.current && track) {
        playCountSentRef.current = true
        api.postPlay(track.id).catch(() => {})
      }
    }
    const onPause = () => setIsPlaying(false)
    const onEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }
    const onTimeUpdate = () => setCurrentTime(audio.currentTime)
    const onDurationChange = () => setDuration(audio.duration || 0)

    audio.addEventListener('play', onPlay)
    audio.addEventListener('pause', onPause)
    audio.addEventListener('ended', onEnded)
    audio.addEventListener('timeupdate', onTimeUpdate)
    audio.addEventListener('durationchange', onDurationChange)

    return () => {
      audio.removeEventListener('play', onPlay)
      audio.removeEventListener('pause', onPause)
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener('timeupdate', onTimeUpdate)
      audio.removeEventListener('durationchange', onDurationChange)
    }
  }, [track])

  const playTrack = async (newTrack: Track) => {
    const audio = audioRef.current
    if (!audio) return
    try {
      const { url } = await api.getStream(newTrack.id)
      audio.src = url
      playCountSentRef.current = false
      setTrack(newTrack)
      setCurrentTime(0)
      setDuration(0)
      await audio.play()
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
    audio.currentTime = (pct / 100) * audio.duration
  }

  const stop = () => {
    const audio = audioRef.current
    if (audio) audio.pause()
    setTrack(null)
    setIsPlaying(false)
  }

  return (
    <PlayerContext.Provider
      value={{
        track,
        isPlaying,
        currentTime,
        duration,
        isComplaintOpen,
        playTrack,
        togglePlay,
        seek,
        openComplaint: () => setIsComplaintOpen(true),
        closeComplaint: () => setIsComplaintOpen(false),
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
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider')
  return ctx
}
