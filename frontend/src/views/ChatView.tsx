import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { onWS } from '@/lib/ws'
import { getInternalUserId } from '@/lib/telegram'
import { ChatBubble } from '@/components/Chat/ChatBubble'
import { ChatInput } from '@/components/Chat/ChatInput'
import { PhotoViewer } from '@/components/Chat/PhotoViewer'
import { Icon } from '@/components/Icon/Icon'
import type { ChatMessage } from '@/types/api'

const ACTIVITY_LABELS: Record<string, string> = {
  typing: 'печатает...',
  recording_audio: 'записывает аудио...',
  sending_photo: 'отправляет фото...',
}

interface Props {
  active: boolean
  conversationId: number | null
  title: string | null
  onBack: () => void
}

export function ChatView({ active, conversationId, title, onBack }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [peerStatus, setPeerStatus] = useState<string>('offline')
  const [peerActivity, setPeerActivity] = useState<string | null>(null)
  const [peerLastSeen, setPeerLastSeen] = useState<number>(0)
  const [viewingPhoto, setViewingPhoto] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const activityTimer = useRef<ReturnType<typeof setTimeout>>()
  const uploadAbort = useRef<AbortController | null>(null)
  const uploadTempId = useRef<number | null>(null)
  const myId = getInternalUserId()

  const mergeIncomingMessage = (
    data: Record<string, unknown>,
  ) => {
    const msgId = Number(
      data.id ?? data.message_id,
    )
    if (!Number.isFinite(msgId)) return
    const nextMessage = {
      id: msgId,
      conversation_id: Number(
        data.conversation_id,
      ),
      sender_id: Number(data.sender_id),
      type: String(data.type || 'text'),
      content: String(data.content || ''),
      reply_to_id:
        typeof data.reply_to_id === 'number'
          ? data.reply_to_id
          : null,
      shared_track_id:
        typeof data.shared_track_id === 'number'
          ? data.shared_track_id
          : null,
      created_at: String(data.created_at),
      attachments: Array.isArray(data.attachments)
        ? data.attachments
        : [],
      reactions: Array.isArray(data.reactions)
        ? data.reactions
        : [],
    } as ChatMessage

    setMessages((prev) => {
      const index = prev.findIndex(
        (msg) => msg.id === msgId,
      )
      if (index === -1) {
        return [...prev, nextMessage]
      }
      return prev.map((msg) =>
        msg.id === msgId
          ? { ...msg, ...nextMessage }
          : msg,
      )
    })
  }

  const applyReactionEvent = (
    data: Record<string, unknown>,
  ) => {
    const msgId = Number(data.message_id)
    const userId = Number(data.user_id)
    const reactionType = String(
      data.reaction_type || '',
    )
    const action = String(data.action || 'add')
    if (
      !Number.isFinite(msgId) ||
      !Number.isFinite(userId) ||
      !reactionType
    ) {
      return
    }

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== msgId) return msg
        const existing = msg.reactions.some(
          (reaction) =>
            reaction.user_id === userId &&
            reaction.reaction_type === reactionType,
        )
        if (action === 'remove') {
          return {
            ...msg,
            reactions: msg.reactions.filter(
              (reaction) =>
                !(
                  reaction.user_id === userId &&
                  reaction.reaction_type ===
                    reactionType
                ),
            ),
          }
        }
        if (existing) return msg
        return {
          ...msg,
          reactions: [
            ...msg.reactions,
            {
              user_id: userId,
              reaction_type: reactionType,
            },
          ],
        }
      }),
    )
  }

  const loadMessages = useCallback(async () => {
    if (!conversationId) return
    setLoading(true)
    try {
      const msgs = await api.getMessages(conversationId)
      setMessages(msgs.reverse())
    } finally {
      setLoading(false)
    }
  }, [conversationId])

  useEffect(() => {
    if (!active || !conversationId) return
    loadMessages()

    api.getChatPresence(conversationId).then((res) => {
      const members = Object.values(res.members)
      if (members.length > 0) {
        const peer = members[0]
        setPeerStatus(peer.status)
        setPeerLastSeen(peer.last_seen)
      } else {
        setPeerStatus('self')
      }
    }).catch(() => {
      setPeerStatus('self')
    })
  }, [active, conversationId, loadMessages])

  useEffect(() => {
    if (!conversationId) return

    const offNew = onWS('message.new', (data) => {
      if (data.conversation_id === conversationId) {
        mergeIncomingMessage(data)
        const msgId = Number(
          data.id ?? data.message_id,
        )
        if (
          Number.isFinite(msgId) &&
          data.sender_id !== myId
        ) {
          api.markRead(conversationId, msgId)
        }
        setPeerActivity(null)
      }
    })

    const offDel = onWS('message.deleted', (data) => {
      if (data.conversation_id === conversationId) {
        setMessages((prev) => prev.filter((m) => m.id !== data.message_id))
      }
    })

    const offActivity = onWS('activity', (data) => {
      if (data.conversation_id === conversationId && data.user_id !== myId) {
        const activity = data.activity as string
        if (activity === 'idle') {
          setPeerActivity(null)
        } else {
          setPeerActivity(activity)
          if (activityTimer.current) clearTimeout(activityTimer.current)
          activityTimer.current = setTimeout(() => setPeerActivity(null), 5000)
        }
      }
    })

    const offReaction = onWS(
      'message.reaction',
      (data) => {
        if (
          data.conversation_id === conversationId
        ) {
          applyReactionEvent(data)
        }
      },
    )

    return () => {
      offNew()
      offDel()
      offActivity()
      offReaction()
      if (activityTimer.current)
        clearTimeout(activityTimer.current)
    }
  }, [conversationId, myId])

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  const addMessage = (msg: ChatMessage) => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === msg.id)) return prev
      return [...prev, msg]
    })
  }

  const handleSend = async (content: string) => {
    if (!conversationId || !content.trim()) return
    const msg = await api.sendMessage(conversationId, content)
    addMessage(msg)
  }

  const handleSendPhoto = async (file: File, caption: string) => {
    if (!conversationId) return

    const localUrl = URL.createObjectURL(file)
    const tempId = -Date.now()
    uploadTempId.current = tempId
    const controller = new AbortController()
    uploadAbort.current = controller

    const placeholder: ChatMessage = {
      id: tempId,
      conversation_id: conversationId,
      sender_id: myId ?? 0,
      type: 'photo',
      content: caption,
      reply_to_id: null,
      shared_track_id: null,
      created_at: new Date().toISOString(),
      attachments: [{
        id: 0,
        file_key: localUrl,
        file_type: 'photo',
      }],
      reactions: [],
      _uploading: true,
    } as ChatMessage & { _uploading?: boolean }
    setMessages((prev) => [...prev, placeholder])

    try {
      const fd = new FormData()
      fd.append('file', file)
      const msg = await api.sendPhoto(conversationId, fd, controller.signal)
      if (caption) {
        await api.sendMessage(conversationId, caption)
      }
      setMessages((prev) =>
        prev.map((m) => (m.id === tempId ? { ...msg, _uploading: false } : m))
      )
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId))
    } finally {
      URL.revokeObjectURL(localUrl)
      uploadAbort.current = null
      uploadTempId.current = null
    }
  }

  const handleCancelUpload = () => {
    uploadAbort.current?.abort()
    if (uploadTempId.current !== null) {
      setMessages((prev) =>
        prev.filter((m) => m.id !== uploadTempId.current)
      )
    }
    uploadAbort.current = null
    uploadTempId.current = null
  }

  const handleSendVoice = async (blob: Blob) => {
    if (!conversationId) return
    const fd = new FormData()
    fd.append('file', blob, 'voice.ogg')
    const msg = await api.sendVoice(conversationId, fd)
    addMessage(msg)
  }

  const handleDelete = async (msgId: number) => {
    await api.deleteMessage(msgId)
    setMessages((prev) => prev.filter((m) => m.id !== msgId))
  }

  const handleReaction = async (msgId: number, type: string) => {
    const hasOwnReaction = messages
      .find((msg) => msg.id === msgId)
      ?.reactions.some(
        (reaction) =>
          reaction.user_id === myId &&
          reaction.reaction_type === type,
      )
    if (hasOwnReaction) {
      await api.removeReaction(msgId, type)
      return
    }
    await api.addReaction(msgId, type)
  }

  const formatLastSeen = (ts: number) => {
    if (!ts) return 'давно'
    const d = new Date(ts * 1000)
    const now = Date.now()
    const diff = (now - d.getTime()) / 1000
    if (diff < 60) return 'только что'
    if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`
    return d.toLocaleDateString()
  }

  const renderStatusLine = () => {
    if (peerStatus === 'self') return null
    if (peerActivity && ACTIVITY_LABELS[peerActivity]) {
      return (
        <span className="chat-status-text activity">
          {ACTIVITY_LABELS[peerActivity]}
        </span>
      )
    }
    if (peerStatus === 'online') {
      return <span className="chat-status-text online">в сети</span>
    }
    if (!peerLastSeen) {
      return (
        <span className="chat-status-text offline">
          не в сети
        </span>
      )
    }
    return (
      <span className="chat-status-text offline">
        был(а) {formatLastSeen(peerLastSeen)}
      </span>
    )
  }

  if (!active) return null

  return (
    <div className="chat-view slide-in">
      <div className="chat-view-header">
        <button className="chat-back-btn" onClick={onBack}>
          <Icon name="chevron" size={20} className="chat-back-icon" />
        </button>
        {peerStatus === 'self' && (
          <div className="chat-header-avatar saved">
            <Icon name="heart" size={20} />
          </div>
        )}
        <div className="chat-header-info">
          <div className="chat-header-top">
            <span className="chat-view-title">
              {title || 'Чат'}
            </span>
            {peerStatus === 'online' && <span className="presence-dot online" />}
          </div>
          <div className="chat-header-status">
            {peerStatus === 'self'
              ? <span className="chat-status-text offline">личное пространство</span>
              : renderStatusLine()}
          </div>
        </div>
      </div>
      <div className="chat-messages" ref={listRef}>
        {loading ? (
          <div className="chat-skeleton">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className={`skeleton-bubble ${i % 2 === 0 ? 'left' : 'right'} shimmer`} />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <div className="chat-empty-state">
            {peerStatus === 'self' ? (
              <>
                <div className="chat-empty-icon">
                  <Icon name="heart" size={32} />
                </div>
                <div className="chat-empty-title">Избранное</div>
                <div className="chat-empty-desc">
                  Сохраняйте сюда важные сообщения, ссылки на треки и заметки
                </div>
              </>
            ) : (
              <div className="chat-empty-desc">Напишите первое сообщение</div>
            )}
          </div>
        ) : (
          messages.map((msg) => (
            <ChatBubble
              key={msg.id}
              message={msg}
              isMine={msg.sender_id === myId}
              onDelete={handleDelete}
              onReaction={handleReaction}
              onCancelUpload={
                (msg as any)._uploading
                  ? handleCancelUpload
                  : undefined
              }
              onViewPhoto={setViewingPhoto}
            />
          ))
        )}
        {peerActivity === 'typing' && (
          <div className="typing-indicator">
            <span /><span /><span />
          </div>
        )}
      </div>
      <ChatInput
        conversationId={conversationId}
        onSend={handleSend}
        onSendPhoto={handleSendPhoto}
        onSendVoice={handleSendVoice}
      />
      {viewingPhoto && (
        <PhotoViewer
          src={viewingPhoto}
          onClose={() => setViewingPhoto(null)}
        />
      )}
    </div>
  )
}
