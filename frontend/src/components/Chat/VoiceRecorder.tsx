import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { safePlay } from '@/lib/safePlay'

interface Props {
  onSend: (blob: Blob) => void
  onCancel: () => void
}

type Phase = 'recording' | 'preview'

function pickMimeType(): string {
  const preferred = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]
  for (const mt of preferred) {
    if (MediaRecorder.isTypeSupported(mt))
      return mt
  }
  return ''
}

export function VoiceRecorder({
  onSend,
  onCancel,
}: Props) {
  const [phase, setPhase] =
    useState<Phase>('recording')
  const [seconds, setSeconds] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')
  const mediaRef = useRef<MediaRecorder | null>(
    null,
  )
  const streamRef = useRef<MediaStream | null>(
    null,
  )
  const chunksRef = useRef<Blob[]>([])
  const timerRef =
    useRef<ReturnType<typeof setInterval>>()
  const blobRef = useRef<Blob | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(
    null,
  )
  const urlRef = useRef<string | null>(null)
  const onCancelRef = useRef(onCancel)
  onCancelRef.current = onCancel

  const stopStream = useCallback(() => {
    streamRef.current
      ?.getTracks()
      .forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const initDone = useRef(false)

  useEffect(() => {
    if (initDone.current) return
    initDone.current = true

    const mimeType = pickMimeType()

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((s) => {
        streamRef.current = s
        const opts: MediaRecorderOptions = {}
        if (mimeType) opts.mimeType = mimeType
        const recorder = new MediaRecorder(
          s,
          opts,
        )
        mediaRef.current = recorder
        chunksRef.current = []

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0)
            chunksRef.current.push(e.data)
        }

        recorder.start()
        timerRef.current = setInterval(
          () => setSeconds((p) => p + 1),
          1000,
        )
      })
      .catch(() => {
        setError('Нет доступа к микрофону')
        setTimeout(
          () => onCancelRef.current(),
          2000,
        )
      })

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = undefined
      }
      stopStream()
      if (urlRef.current)
        URL.revokeObjectURL(urlRef.current)
    }
  }, [stopStream])

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = undefined
    }
  }, [])

  const handleStop = () => {
    const recorder = mediaRef.current
    if (
      !recorder ||
      recorder.state !== 'recording'
    )
      return

    clearTimer()
    recorder.onstop = () => {
      const mt =
        recorder.mimeType || 'audio/webm'
      const blob = new Blob(chunksRef.current, {
        type: mt,
      })
      blobRef.current = blob
      urlRef.current = URL.createObjectURL(blob)
      stopStream()
      setPhase('preview')
    }
    recorder.stop()
  }

  const handlePlayPause = () => {
    if (!urlRef.current) return
    if (!audioRef.current) {
      audioRef.current = new Audio(
        urlRef.current,
      )
      audioRef.current.onended = () =>
        setPlaying(false)
    }
    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.currentTime = 0
      void safePlay(audioRef.current)
    }
    setPlaying(!playing)
  }

  const handleSend = () => {
    audioRef.current?.pause()
    if (blobRef.current) {
      onSend(blobRef.current)
    }
  }

  const handleCancel = () => {
    audioRef.current?.pause()
    mediaRef.current?.stop()
    if (timerRef.current)
      clearInterval(timerRef.current)
    stopStream()
    onCancel()
  }

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  if (error) {
    return (
      <div className="voice-recorder">
        <span className="voice-timer">
          {error}
        </span>
      </div>
    )
  }

  if (phase === 'preview') {
    return (
      <div className="voice-recorder">
        <MotionPress
          type="button"
          variant="icon"
          haptic="light"
          className="voice-cancel-btn"
          onClick={handleCancel}
        >
          <Icon name="x" size={20} />
        </MotionPress>
        <MotionPress
          type="button"
          variant="icon"
          haptic="medium"
          className="voice-play-preview"
          onClick={handlePlayPause}
        >
          <MorphIcon
            name={playing ? 'pause' : 'play'}
            size={18}
            filled
          />
        </MotionPress>
        <div className="voice-recording-indicator">
          <span className="voice-timer">
            {formatTime(seconds)}
          </span>
        </div>
        <MotionPress
          type="button"
          variant="primary"
          haptic="medium"
          className="voice-send-btn"
          onClick={handleSend}
        >
          <Icon name="send" size={20} />
        </MotionPress>
      </div>
    )
  }

  return (
    <div className="voice-recorder">
      <MotionPress
        type="button"
        variant="icon"
        haptic="light"
        className="voice-cancel-btn"
        onClick={handleCancel}
      >
        <Icon name="x" size={20} />
      </MotionPress>
      <div className="voice-recording-indicator">
        <span className="voice-pulse" />
        <span className="voice-timer">
          {formatTime(seconds)}
        </span>
      </div>
      <MotionPress
        type="button"
        variant="primary"
        haptic="medium"
        className="voice-send-btn"
        onClick={handleStop}
      >
        <Icon name="check" size={20} />
      </MotionPress>
    </div>
  )
}
