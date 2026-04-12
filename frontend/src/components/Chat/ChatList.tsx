import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { ChatListItem } from '@/types/api'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  items: ChatListItem[]
  onOpenChat: (convId: number, title?: string) => void
}

export function ChatList({ items, onOpenChat }: Props) {
  const [onlineMap, setOnlineMap] = useState<Record<number, boolean>>({})

  useEffect(() => {
    if (items.length === 0) return
    let cancelled = false
    Promise.all(
      items.map((item) =>
        api
          .getChatPresence(item.conversation.id)
          .then((res) => {
            const members = Object.values(res.members)
            const online = members.some((m) => m.status === 'online')
            return [item.conversation.id, online] as const
          })
          .catch(() => [item.conversation.id, false] as const),
      ),
    ).then((results) => {
      if (cancelled) return
      const map: Record<number, boolean> = {}
      for (const [id, online] of results) map[id] = online
      setOnlineMap(map)
    })
    return () => { cancelled = true }
  }, [items])

  return (
    <div className="chat-list">
      {items.map((item, i) => (
        <button
          key={item.conversation.id}
          className="chat-list-item fade-in-stagger"
          style={{ animationDelay: `${i * 50}ms` }}
          onClick={() => onOpenChat(
            item.conversation.id,
            item.conversation.title || undefined,
          )}
        >
          <div className="chat-list-avatar">
            <Icon
              name={
                item.conversation.type === 'saved'
                  ? 'heart'
                  : 'user'
              }
              size={24}
            />
            {onlineMap[item.conversation.id] && (
              <span className="presence-dot online list-dot" />
            )}
          </div>
          <div className="chat-list-info">
            <span className="chat-list-name">
              {item.conversation.title || `Chat #${item.conversation.id}`}
              {item.member.is_pinned && (
                <Icon name="pin" size={12} className="chat-pin-icon" />
              )}
            </span>
            <span className="chat-list-preview">
              {item.last_message_at
                ? new Date(item.last_message_at).toLocaleString()
                : 'Нет сообщений'}
            </span>
          </div>
          <Icon name="chevron" size={16} className="chat-list-chevron" />
        </button>
      ))}
    </div>
  )
}
