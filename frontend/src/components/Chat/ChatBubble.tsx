import { useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { VoicePlayer } from '@/components/Chat/VoicePlayer'
import type { ChatMessage } from '@/types/api'

interface Props {
  message: ChatMessage
  isMine: boolean
  onDelete: (id: number) => void
  onReaction: (id: number, type: string) => void
}

const REACTIONS = ['thumbs-up', 'heart', 'music', 'sparkle']

export function ChatBubble({ message, isMine, onDelete, onReaction }: Props) {
  const [showActions, setShowActions] = useState(false)
  const [showReactions, setShowReactions] = useState(false)

  const handleLongPress = () => {
    try { window.navigator?.vibrate?.(10) } catch {}
    setShowActions(true)
  }

  const photoAtt = message.attachments?.find((a) => a.file_type === 'photo')
  const voiceAtt = message.attachments?.find((a) => a.file_type === 'voice')

  return (
    <div
      className={`chat-bubble ${isMine ? 'mine' : 'theirs'} msg-appear`}
      onContextMenu={(e) => { e.preventDefault(); handleLongPress() }}
    >
      {message.reply_to_id && (
        <div className="bubble-reply">Reply to #{message.reply_to_id}</div>
      )}

      {photoAtt && (
        <div className="bubble-photo">
          <img
            src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(photoAtt.file_key)}`}
            alt=""
            className="bubble-photo-img"
            loading="lazy"
          />
        </div>
      )}

      {voiceAtt && (
        <VoicePlayer
          fileKey={voiceAtt.file_key}
          duration={voiceAtt.duration_seconds ?? 0}
          waveform={voiceAtt.waveform ?? []}
        />
      )}

      {message.content && (
        <div className="bubble-text">{message.content}</div>
      )}

      <div className="bubble-meta">
        <span className="bubble-time">
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
        {message.reactions?.length > 0 && (
          <div className="bubble-reactions">
            {message.reactions.map((r, i) => (
              <span key={i} className="bubble-reaction bounce-in">
                <Icon name={r.reaction_type} size={14} />
              </span>
            ))}
          </div>
        )}
      </div>

      {showActions && (
        <div className="msg-actions-overlay" onClick={() => setShowActions(false)}>
          <div className="msg-actions scale-in" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => { setShowReactions(true); setShowActions(false) }}>
              <Icon name="sparkle" size={16} /> Реакция
            </button>
            <button onClick={() => { onDelete(message.id); setShowActions(false) }}>
              <Icon name="trash" size={16} /> Удалить
            </button>
          </div>
        </div>
      )}

      {showReactions && (
        <div className="reaction-picker-overlay" onClick={() => setShowReactions(false)}>
          <div className="reaction-picker scale-in" onClick={(e) => e.stopPropagation()}>
            {REACTIONS.map((r) => (
              <button
                key={r}
                className="reaction-btn"
                onClick={() => { onReaction(message.id, r); setShowReactions(false) }}
              >
                <Icon name={r} size={24} />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
