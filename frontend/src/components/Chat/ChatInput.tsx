import { useCallback, useRef, useState } from 'react'
import { sendWS } from '@/lib/ws'
import { Icon } from '@/components/Icon/Icon'
import { VoiceRecorder } from '@/components/Chat/VoiceRecorder'

interface Props {
  conversationId: number | null
  onSend: (content: string) => void
  onSendPhoto: (file: File) => void
  onSendVoice: (blob: Blob) => void
}

export function ChatInput({ conversationId, onSend, onSendPhoto, onSendVoice }: Props) {
  const [text, setText] = useState('')
  const [recording, setRecording] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const typingTimer = useRef<ReturnType<typeof setTimeout>>()

  const emitActivity = useCallback((activity: string) => {
    if (!conversationId) return
    sendWS({ event: 'activity', conversation_id: conversationId, activity })
  }, [conversationId])

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    if (typingTimer.current) clearTimeout(typingTimer.current)
    emitActivity('typing')
    typingTimer.current = setTimeout(() => emitActivity('idle'), 3000)
  }

  const handleSubmit = () => {
    if (!text.trim()) return
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

  const handlePhoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      emitActivity('sending_photo')
      onSendPhoto(file)
    }
    e.target.value = ''
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
        accept="image/*"
        hidden
        onChange={handlePhoto}
      />
      <textarea
        className="chat-input-text"
        value={text}
        onChange={handleTextChange}
        onKeyDown={handleKeyDown}
        placeholder="Сообщение..."
        rows={1}
      />
      {text.trim() ? (
        <button className="chat-input-btn chat-send-btn" onClick={handleSubmit}>
          <Icon name="send" size={20} />
        </button>
      ) : (
        <button className="chat-input-btn" onClick={handleStartRecording}>
          <Icon name="mic" size={20} />
        </button>
      )}
    </div>
  )
}
