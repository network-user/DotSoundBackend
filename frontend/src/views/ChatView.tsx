import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { onWS } from '@/lib/ws'
import { getInternalUserId } from '@/lib/telegram'
import { ChatBubble } from '@/components/Chat/ChatBubble'
import { ChatInput } from '@/components/Chat/ChatInput'
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
  onBack: () => void
}

export function ChatView({ active, conversationId, onBack }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [peerStatus, setPeerStatus] = useState<string>('offline')
  const [peerActivity, setPeerActivity] = useState<string | null>(null)
  const [peerLastSeen, setPeerLastSeen] = useState<number>(0)
  const listRef = useRef<HTMLDivElement>(null)
  const activityTimer = useRef<ReturnType<typeof setTimeout>>()
  const myId = getInternalUserId()

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
      }
    })
  }, [active, conversationId, loadMessages])

  useEffect(() => {
    if (!conversationId) return

    const offNew = onWS('message.new', (data) => {
      if (data.conversation_id === conversationId) {
        setMessages((prev) => [...prev, data as unknown as ChatMessage])
        if (data.sender_id !== myId) {
          api.markRead(conversationId, data.message_id as number)
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

    return () => { offNew(); offDel(); offActivity() }
  }, [conversationId, myId])

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = async (content: string) => {
    if (!conversationId || !content.trim()) return
    await api.sendMessage(conversationId, content)
  }

  const handleSendPhoto = async (file: File) => {
    if (!conversationId) return
    const fd = new FormData()
    fd.append('file', file)
    await api.sendPhoto(conversationId, fd)
  }

  const handleSendVoice = async (blob: Blob) => {
    if (!conversationId) return
    const fd = new FormData()
    fd.append('file', blob, 'voice.ogg')
    await api.sendVoice(conversationId, fd)
  }

  const handleDelete = async (msgId: number) => {
    await api.deleteMessage(msgId)
  }

  const handleReaction = async (msgId: number, type: string) => {
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
        <div className="chat-header-info">
          <div className="chat-header-top">
            <span className="chat-view-title">Чат</span>
            {peerStatus === 'online' && <span className="presence-dot online" />}
          </div>
          <div className="chat-header-status">
            {renderStatusLine()}
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
          <div className="empty-state">Нет сообщений</div>
        ) : (
          messages.map((msg) => (
            <ChatBubble
              key={msg.id}
              message={msg}
              isMine={msg.sender_id === myId}
              onDelete={handleDelete}
              onReaction={handleReaction}
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
    </div>
  )
}
