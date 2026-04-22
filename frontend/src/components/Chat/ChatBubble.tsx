import { useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { VoicePlayer } from '@/components/Chat/VoicePlayer'
import type { ChatMessage } from '@/types/api'

interface Props {
  message: ChatMessage & {
    _uploading?: boolean
    is_system?: boolean
    sender_role?: 'admin' | 'user' | 'system'
  }
  isMine: boolean
  onDelete: (id: number) => void
  onReaction: (id: number, type: string) => void
  onCancelUpload?: () => void
  onViewPhoto?: (src: string) => void
}

const REACTIONS = [
  'thumbs-up',
  'heart',
  'music',
  'sparkle',
]

export function ChatBubble({
  message,
  isMine,
  onDelete,
  onReaction,
  onCancelUpload,
  onViewPhoto,
}: Props) {
  const [showBar, setShowBar] = useState(false)
  const [showReactions, setShowReactions] =
    useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)

  const photoAtt = message.attachments?.find(
    (a) => a.file_type === 'photo',
  )
  const voiceAtt = message.attachments?.find(
    (a) => a.file_type === 'voice',
  )

  const isLocal =
    photoAtt?.file_key?.startsWith('blob:')
  const photoSrc = isLocal
    ? photoAtt!.file_key
    : photoAtt
      ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(photoAtt.file_key)}`
      : ''

  const handleTap = () => {
    if (message._uploading) return
    setShowBar((p) => !p)
  }

  const handlePhotoClick = () => {
    if (
      message._uploading ||
      !imgLoaded ||
      !photoSrc
    )
      return
    onViewPhoto?.(photoSrc)
  }

  const isSystem =
    message.is_system === true ||
    message.sender_role === 'admin' ||
    message.sender_role === 'system'

  if (isSystem) {
    return (
      <div className="chat-msg system">
        <div className="chat-msg-system-card">
          <span className="chat-msg-system-icon">
            <Icon name="shield" size={16} />
          </span>
          <div className="chat-msg-system-body">
            <span className="chat-msg-system-label">
              Команда .sound
            </span>
            {message.content}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`chat-bubble-wrap ${isMine ? 'mine' : 'theirs'}`}
    >
      <div
        className={`chat-bubble ${isMine ? 'mine' : 'theirs'} msg-appear ${message._uploading ? 'uploading' : ''}`}
        onClick={handleTap}
      >
        {message.reply_to_id && (
          <div className="bubble-reply">
            Reply to #{message.reply_to_id}
          </div>
        )}

        {photoAtt && (
          <div
            className="bubble-photo"
            onClick={(e) => {
              e.stopPropagation()
              handlePhotoClick()
            }}
          >
            {!imgLoaded && !isLocal && (
              <div className="bubble-photo-placeholder shimmer" />
            )}
            <img
              src={photoSrc}
              alt=""
              className={`bubble-photo-img ${imgLoaded ? 'loaded' : ''}`}
              loading="lazy"
              onLoad={() => setImgLoaded(true)}
            />
            {message._uploading && (
              <div className="bubble-photo-upload">
                <div className="upload-spinner" />
                {onCancelUpload && (
                  <button
                    className="upload-cancel-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      onCancelUpload()
                    }}
                  >
                    <Icon name="x" size={16} />
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {voiceAtt && (
          <VoicePlayer
            fileKey={voiceAtt.file_key}
            duration={
              voiceAtt.duration_seconds ?? 0
            }
            waveform={voiceAtt.waveform ?? []}
          />
        )}

        {message.content && (
          <div className="bubble-text">
            {message.content}
          </div>
        )}

        <div className="bubble-meta">
          {message._uploading ? (
            <span className="bubble-time uploading-text">
              отправка...
            </span>
          ) : (
            <span className="bubble-time">
              {new Date(
                message.created_at,
              ).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}
          {message.reactions?.length > 0 && (
            <div className="bubble-reactions">
              {message.reactions.map((r, i) => (
                <span
                  key={i}
                  className="bubble-reaction bounce-in"
                >
                  <Icon
                    name={r.reaction_type}
                    size={14}
                  />
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {showBar && !message._uploading && (
        <div
          className={`bubble-action-bar ${isMine ? 'mine' : 'theirs'} scale-in`}
        >
          <button
            className="bubble-action-btn"
            onClick={() => {
              setShowReactions((p) => !p)
              setShowBar(false)
            }}
          >
            <Icon name="sparkle" size={16} />
          </button>
          <button
            className="bubble-action-btn"
            onClick={() => {
              onDelete(message.id)
              setShowBar(false)
            }}
          >
            <Icon name="trash" size={16} />
          </button>
        </div>
      )}

      {showReactions && (
        <div
          className="reaction-picker-overlay"
          onClick={() => setShowReactions(false)}
        >
          <div
            className="reaction-picker scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            {REACTIONS.map((r) => (
              <button
                key={r}
                className="reaction-btn"
                onClick={() => {
                  onReaction(message.id, r)
                  setShowReactions(false)
                }}
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
