import { useRef, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  fileKey: string
  duration: number
  waveform: number[]
}

const SPEEDS = [1, 1.5, 2]

export function VoicePlayer({ fileKey, duration, waveform }: Props) {
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [speedIdx, setSpeedIdx] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const togglePlay = () => {
    if (!audioRef.current) {
      const audio = new Audio(`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(fileKey)}`)
      audio.playbackRate = SPEEDS[speedIdx]
      audio.ontimeupdate = () => {
        if (audio.duration) setProgress(audio.currentTime / audio.duration)
      }
      audio.onended = () => { setPlaying(false); setProgress(0) }
      audioRef.current = audio
    }

    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }
    setPlaying(!playing)
  }

  const cycleSpeed = () => {
    const next = (speedIdx + 1) % SPEEDS.length
    setSpeedIdx(next)
    if (audioRef.current) audioRef.current.playbackRate = SPEEDS[next]
  }

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

  const barCount = waveform.length || 40

  return (
    <div className="voice-player">
      <button className="voice-play-btn" onClick={togglePlay}>
        <Icon name={playing ? 'pause' : 'play'} size={18} />
      </button>
      <div className="voice-waveform">
        {Array.from({ length: barCount }).map((_, i) => {
          const val = waveform[i] ?? 0.2
          const filled = i / barCount <= progress
          return (
            <span
              key={i}
              className={`waveform-bar ${filled ? 'filled' : ''}`}
              style={{ height: `${Math.max(val * 100, 8)}%` }}
            />
          )
        })}
      </div>
      <div className="voice-meta">
        <span className="voice-duration">{formatTime(duration)}</span>
        <button className="voice-speed-btn" onClick={cycleSpeed}>
          {SPEEDS[speedIdx]}x
        </button>
      </div>
    </div>
  )
}
