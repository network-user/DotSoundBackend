import { useEffect, useRef, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  onSend: (blob: Blob) => void
  onCancel: () => void
}

export function VoiceRecorder({ onSend, onCancel }: Props) {
  const [seconds, setSeconds] = useState(0)
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval>>()

  useEffect(() => {
    let stream: MediaStream | null = null

    navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => {
      stream = s
      const recorder = new MediaRecorder(s, { mimeType: 'audio/webm;codecs=opus' })
      mediaRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.start()
      timerRef.current = setInterval(() => setSeconds((p) => p + 1), 1000)
    }).catch(() => onCancel())

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [onCancel])

  const handleSend = () => {
    const recorder = mediaRef.current
    if (!recorder) return

    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      onSend(blob)
    }
    recorder.stop()
    if (timerRef.current) clearInterval(timerRef.current)
  }

  const handleCancel = () => {
    mediaRef.current?.stop()
    if (timerRef.current) clearInterval(timerRef.current)
    onCancel()
  }

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="voice-recorder">
      <button className="voice-cancel-btn" onClick={handleCancel}>
        <Icon name="x" size={20} />
      </button>
      <div className="voice-recording-indicator">
        <span className="voice-pulse" />
        <span className="voice-timer">{formatTime(seconds)}</span>
      </div>
      <button className="voice-send-btn" onClick={handleSend}>
        <Icon name="send" size={20} />
      </button>
    </div>
  )
}
