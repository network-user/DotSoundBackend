import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ChatListItem } from '@/types/api'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  items: ChatListItem[]
}

export function ChatList({ items }: Props) {
  const navigate = useNavigate()
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

  const chatDisplayName = (
    item: ChatListItem,
  ) => {
    if (item.peer) {
      return (
        item.peer.display_name ||
        item.peer.first_name +
          (item.peer.last_name
            ? ` ${item.peer.last_name}`
            : '')
      )
    }
    return (
      item.conversation.title ||
      `Чат #${item.conversation.id}`
    )
  }

  return (
    <div className="chat-list">
      {items.map((item, i) => (
        <button
          key={item.conversation.id}
          className="chat-list-item fade-in-stagger"
          style={{
            animationDelay: `${i * 50}ms`,
          }}
          onClick={() =>
            navigate(
              `/chats/${item.conversation.id}`,
              {
                state: {
                  title: chatDisplayName(item),
                },
              },
            )
          }
        >
          <div className="chat-list-avatar">
            <Icon
              name={
                item.conversation.type ===
                'saved'
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
              {chatDisplayName(item)}
              {item.member.is_pinned && (
                <Icon
                  name="pin"
                  size={12}
                  className="chat-pin-icon"
                />
              )}
            </span>
            <span className="chat-list-preview">
              {item.last_message_at
                ? new Date(
                    item.last_message_at,
                  ).toLocaleString()
                : 'Нет сообщений'}
            </span>
          </div>
          <Icon
            name="chevron"
            size={16}
            className="chat-list-chevron"
          />
        </button>
      ))}
    </div>
  )
}
