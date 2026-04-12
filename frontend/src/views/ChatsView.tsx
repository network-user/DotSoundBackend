import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { ChatList } from '@/components/Chat/ChatList'
import type { ChatListItem } from '@/types/api'

interface Props {
  active: boolean
  onOpenChat: (convId: number) => void
}

export function ChatsView({ active, onOpenChat }: Props) {
  const [chats, setChats] = useState<ChatListItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!active) return
    setLoading(true)
    api.listChats().then(setChats).finally(() => setLoading(false))
  }, [active])

  return (
    <div className={`view${active ? ' active' : ''}`}>
      <div className="view-header">
        <h2 className="view-title">Чаты</h2>
      </div>
      {loading ? (
        <div className="chat-skeleton">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton-chat-item shimmer" />
          ))}
        </div>
      ) : chats.length === 0 ? (
        <div className="empty-state">Нет чатов</div>
      ) : (
        <ChatList items={chats} onOpenChat={onOpenChat} />
      )}
    </div>
  )
}
