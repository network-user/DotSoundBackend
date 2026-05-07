import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ChatListItem } from '@/types/api'
import { Icon } from '@/components/Icon/Icon'
import { SwipeRow } from '@/components/ui/SwipeRow'
import {
  LongPressMenu,
  type LongPressMenuItem,
} from '@/components/ui/LongPressMenu'
import { showIsland } from '@/lib/island'

interface Props {
  items: ChatListItem[]
}

export function ChatList({ items }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [onlineMap, setOnlineMap] = useState<
    Record<number, boolean>
  >({})

  useEffect(() => {
    if (items.length === 0) return
    let cancelled = false
    Promise.all(
      items.map((item) =>
        api
          .getChatPresence(item.conversation.id)
          .then((res) => {
            const members = Object.values(res.members)
            const online = members.some(
              (m) => m.status === 'online',
            )
            return [item.conversation.id, online] as const
          })
          .catch(() =>
            [item.conversation.id, false] as const,
          ),
      ),
    ).then((results) => {
      if (cancelled) return
      const map: Record<number, boolean> = {}
      for (const [id, online] of results) {
        map[id] = online
      }
      setOnlineMap(map)
    })
    return () => {
      cancelled = true
    }
  }, [items])

  const chatDisplayName = (item: ChatListItem) => {
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
      t('redesign.chats.chatNumber', {
        id: item.conversation.id,
      })
    )
  }

  const openChat = (item: ChatListItem) => {
    navigate(`/chats/${item.conversation.id}`, {
      state: { title: chatDisplayName(item) },
    })
  }

  const buildMenuItems = (
    item: ChatListItem,
  ): LongPressMenuItem[] => {
    const soon = () =>
      showIsland({ kind: 'toast', title: t('redesign.tracks.chatActionSoon'), durationMs: 2000 })
    return [
      {
        id: 'mute',
        label: t('redesign.tracks.chatMenuMute'),
        icon: 'volume-off',
        onPick: soon,
      },
      {
        id: 'pin',
        label: item.member.is_pinned
          ? t('redesign.tracks.chatMenuUnpin')
          : t('redesign.tracks.chatMenuPin'),
        icon: 'pin',
        onPick: soon,
      },
      {
        id: 'unread',
        label: t('redesign.tracks.chatMenuMarkUnread'),
        icon: 'eye',
        onPick: soon,
      },
      {
        id: 'delete',
        label: t('redesign.tracks.chatMenuDelete'),
        icon: 'trash',
        destructive: true,
        onPick: soon,
      },
    ]
  }

  return (
    <div className="chat-list re-chats-root">
      {items.map((item, i) => (
        <div key={item.conversation.id} className="re-chats-row">
          <SwipeRow
            leftAction={{
              icon: 'pin',
              label: t('redesign.tracks.chatPin'),
              onTrigger: () => {
                showIsland({ kind: 'toast', title: t('redesign.tracks.chatActionSoon'), durationMs: 2000 })
              },
            }}
            rightAction={{
              icon: 'bookmark',
              label: t('redesign.tracks.chatArchive'),
              onTrigger: () => {
                showIsland({ kind: 'toast', title: t('redesign.tracks.chatActionSoon'), durationMs: 2000 })
              },
            }}
          >
            <LongPressMenu items={buildMenuItems(item)}>
              <div
                className="chat-list-item fade-in-stagger re-chats-item-inner"
                role="button"
                tabIndex={0}
                style={{
                  animationDelay: `${i * 50}ms`,
                }}
                onClick={() => openChat(item)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    openChat(item)
                  }
                }}
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
                      : t('redesign.chats.noMessages')}
                  </span>
                </div>
                <Icon
                  name="chevron"
                  size={16}
                  className="chat-list-chevron"
                />
              </div>
            </LongPressMenu>
          </SwipeRow>
        </div>
      ))}
    </div>
  )
}
