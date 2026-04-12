import { useCallback, useRef, useState } from 'react'
import { sendWS } from '@/lib/ws'
import { Icon } from '@/components/Icon/Icon'
import { PhotoPreview } from '@/components/Chat/PhotoPreview'
import { VoiceRecorder } from '@/components/Chat/VoiceRecorder'

const MAX_MSG_LENGTH = 4096
const COUNTER_THRESHOLD = 3800
const MAX_IMAGE_MB = 10

interface Props {
  conversationId: number | null
  onSend: (content: string) => void
  onSendPhoto: (file: File, caption: string) => void
  onSendVoice: (blob: Blob) => void
}

export function ChatInput({
  conversationId,
  onSend,
  onSendPhoto,
  onSendVoice,
}: Props) {
  const [text, setText] = useState('')
  const [recording, setRecording] = useState(false)
  const [pendingPhoto, setPendingPhoto] = useState<File | null>(null)
  const [fileError, setFileError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const typingTimer = useRef<ReturnType<typeof setTimeout>>()

  const isOverLimit = text.length > MAX_MSG_LENGTH
  const showCounter = text.length >= COUNTER_THRESHOLD

  const emitActivity = useCallback(
    (activity: string) => {
      if (!conversationId) return
      sendWS({
        event: 'activity',
        conversation_id: conversationId,
        activity,
      })
    },
    [conversationId],
  )

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    if (typingTimer.current) clearTimeout(typingTimer.current)
    emitActivity('typing')
    typingTimer.current = setTimeout(() => emitActivity('idle'), 3000)
  }

  const handleSubmit = () => {
    if (!text.trim() || isOverLimit) return
    if (typingTimer.current) clearTimeout(typingTimer.current)
    emitActivity('idle')
    onSend(text.trim())
    setText('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError('')
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    const sizeMb = file.size / 1024 / 1024
    if (sizeMb > MAX_IMAGE_MB) {
      setFileError(`Файл слишком большой (${sizeMb.toFixed(1)} МБ, макс ${MAX_IMAGE_MB} МБ)`)
      setTimeout(() => setFileError(''), 4000)
      return
    }
    setPendingPhoto(file)
  }

  const handlePhotoSend = (file: File, caption: string) => {
    emitActivity('sending_photo')
    onSendPhoto(file, caption)
    setPendingPhoto(null)
  }

  const handleStartRecording = () => {
    emitActivity('recording_audio')
    setRecording(true)
  }

  const handleVoiceSend = (blob: Blob) => {
    emitActivity('idle')
    onSendVoice(blob)
    setRecording(false)
  }

  const handleVoiceCancel = () => {
    emitActivity('idle')
    setRecording(false)
  }

  if (pendingPhoto) {
    return (
      <PhotoPreview
        file={pendingPhoto}
        onSend={handlePhotoSend}
        onCancel={() => setPendingPhoto(null)}
      />
    )
  }

  if (recording) {
    return (
      <VoiceRecorder
        onSend={handleVoiceSend}
        onCancel={handleVoiceCancel}
      />
    )
  }

  return (
    <div className="chat-input-bar">
      <button
        className="chat-input-btn"
        onClick={() => fileRef.current?.click()}
      >
        <Icon name="image" size={20} />
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        hidden
        onChange={handleFileSelect}
      />
      <div className="chat-input-wrap">
        <textarea
          className="chat-input-text"
          value={text}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          placeholder="Сообщение..."
          rows={1}
        />
        {showCounter && (
          <span className={`char-counter ${isOverLimit ? 'over' : ''}`}>
            {text.length}/{MAX_MSG_LENGTH}
          </span>
        )}
      </div>
      {text.trim() ? (
        <button
          className="chat-input-btn chat-send-btn"
          onClick={handleSubmit}
          disabled={isOverLimit}
        >
          <Icon name="send" size={20} />
        </button>
      ) : (
        <button
          className="chat-input-btn"
          onClick={handleStartRecording}
        >
          <Icon name="mic" size={20} />
        </button>
      )}
      {fileError && (
        <div className="chat-file-error fade-in">{fileError}</div>
      )}
    </div>
  )
}
