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
  playTrack: (track: Track) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  openComplaint: () => void
  closeComplaint: () => void
  stop: () => void
}

const PlayerContext = createContext<PlayerContextValue | null>(null)

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const scIframeRef = useRef<HTMLIFrameElement>(null)
  const scWidgetRef = useRef<SCWidgetInstance | null>(null)

  const [track, setTrack] = useState<Track | null>(null)
  const [mode, setMode] = useState<'internal' | 'soundcloud'>('internal')
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(() => {
    const saved = localStorage.getItem('player-volume')
    return saved ? parseFloat(saved) : 0.8
  })
  const [isComplaintOpen, setIsComplaintOpen] = useState(false)
  const playCountSentRef = useRef(false)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || mode !== 'internal') return

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
  }, [track, mode])

  useEffect(() => {
    const audio = audioRef.current
    if (audio) audio.volume = volume
    localStorage.setItem('player-volume', volume.toString())
  }, [volume])

  const bindScWidget = (newTrack: Track) => {
    const iframe = scIframeRef.current
    if (!iframe || typeof SC === 'undefined') return

    scWidgetRef.current = SC.Widget(iframe)
    const widget = scWidgetRef.current

    widget.bind(SC.Widget.Events.PLAY, () => {
      setIsPlaying(true)
      if (!playCountSentRef.current) {
        playCountSentRef.current = true
        api.postPlay(newTrack.id).catch(() => {})
      }
    })

    widget.bind(SC.Widget.Events.PAUSE, () => {
      setIsPlaying(false)
    })

    widget.bind(SC.Widget.Events.FINISH, () => {
      setIsPlaying(false)
      setCurrentTime(0)
    })

    widget.bind(SC.Widget.Events.PLAY_PROGRESS, (e) => {
      if (!e) return
      setCurrentTime(e.currentPosition / 1000)
      if (e.duration) setDuration(e.duration / 1000)
    })
  }

  const setVolume = (v: number) => {
    setVolumeState(Math.max(0, Math.min(1, v)))
  }

  const playTrack = async (newTrack: Track) => {
    playCountSentRef.current = false
    setTrack(newTrack)
    setCurrentTime(0)
    setDuration(newTrack.duration_seconds ?? 0)

    if (newTrack.source === 'soundcloud') {
      const audio = audioRef.current
      if (audio) {
        audio.pause()
        audio.src = ''
      }
      setMode('soundcloud')
      try {
        const { url } = await api.getStream(newTrack.id)
        const iframe = scIframeRef.current
        if (!iframe) return
        iframe.src = url
        bindScWidget(newTrack)
      } catch (e) {
        console.error('sc playTrack error', e)
      }
      return
    }

    setMode('internal')
    if (scWidgetRef.current) {
      try { scWidgetRef.current.pause() } catch { }
      scWidgetRef.current = null
    }
    const scIframe = scIframeRef.current
    if (scIframe) scIframe.src = ''

    const audio = audioRef.current
    if (!audio) return
    try {
      const { url } = await api.getStream(newTrack.id)
      audio.src = url
      audio.volume = volume
      await audio.play()
    } catch (e) {
      console.error('playTrack error', e)
    }
  }

  const togglePlay = () => {
    if (mode === 'soundcloud') {
      scWidgetRef.current?.toggle()
      return
    }
    const audio = audioRef.current
    if (!audio || !track) return
    if (audio.paused) audio.play()
    else audio.pause()
  }

  const seek = (pct: number) => {
    if (mode === 'soundcloud') {
      if (scWidgetRef.current && duration) {
        scWidgetRef.current.seekTo(pct * duration * 10)
      }
      return
    }
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    audio.currentTime = (pct / 100) * audio.duration
  }

  const stop = () => {
    if (mode === 'soundcloud') {
      try { scWidgetRef.current?.pause() } catch { }
      scWidgetRef.current = null
      const scIframe = scIframeRef.current
      if (scIframe) scIframe.src = ''
    } else {
      const audio = audioRef.current
      if (audio) audio.pause()
    }
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
        playTrack,
        togglePlay,
        seek,
        openComplaint: () => setIsComplaintOpen(true),
        closeComplaint: () => setIsComplaintOpen(false),
        stop,
      }}
    >
      <audio ref={audioRef} preload="none" />
      <iframe
        ref={scIframeRef}
        style={{ display: 'none', width: 0, height: 0, border: 'none' }}
        allow="autoplay"
        scrolling="no"
        title="sc-player"
      />
      {children}
    </PlayerContext.Provider>
  )
}

export function usePlayer() {
  const ctx = useContext(PlayerContext)
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider')
  return ctx
}
