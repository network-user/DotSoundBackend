import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { ChatList } from '@/components/Chat/ChatList'
import { Icon } from '@/components/Icon/Icon'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import type { ChatListItem } from '@/types/api'

interface UserResult {
  id: number
  username: string | null
  first_name: string
  last_name: string | null
  display_name: string | null
  avatar_key: string | null
}

interface Props {
  active: boolean
  onOpenChat: (convId: number, title?: string) => void
}

export function ChatsView({ active, onOpenChat }: Props) {
  const [chats, setChats] = useState<ChatListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<UserResult[]>([])
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  const loadChats = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.listChats()
      setChats(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!active) return
    loadChats()
  }, [active, loadChats])

  const handleSearch = (value: string) => {
    setQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!value.trim()) {
      setSearchResults([])
      setSearching(false)
      return
    }
    setSearching(true)
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await api.searchUsers(value.trim())
        setSearchResults(results)
      } finally {
        setSearching(false)
      }
    }, 300)
  }

  const handleOpenSaved = async () => {
    const res = await api.getSavedChat()
    onOpenChat(res.conversation.id, 'Избранное')
  }

  const handleSelectUser = async (userId: number) => {
    const res = await api.createDM(userId)
    const user = searchResults.find((u) => u.id === userId)
    const name = user
      ? (user.display_name || user.first_name + (user.last_name ? ` ${user.last_name}` : ''))
      : undefined
    setQuery('')
    setSearchResults([])
    onOpenChat(res.conversation.id, name)
  }

  return (
    <div className={`view${active ? ' active' : ''}`}>
      <div className="chats-header">
        <h2 className="chats-title">Чаты</h2>
        <NotificationBell />
      </div>

      <div className="chats-search-bar">
        <Icon name="search" size={16} className="chats-search-icon" />
        <input
          className="chats-search-input"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Поиск по имени или username..."
        />
        {query && (
          <button
            className="chats-search-clear"
            onClick={() => { setQuery(''); setSearchResults([]) }}
          >
            <Icon name="x" size={14} />
          </button>
        )}
      </div>

      {query.trim() ? (
        <div className="chats-search-results">
          {searching ? (
            <div className="chat-skeleton">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="skeleton-chat-item shimmer" />
              ))}
            </div>
          ) : searchResults.length === 0 ? (
            <div className="chats-empty">Никого не найдено</div>
          ) : (
            searchResults.map((u, i) => (
              <button
                key={u.id}
                className="chat-list-item fade-in-stagger"
                style={{ animationDelay: `${i * 50}ms` }}
                onClick={() => handleSelectUser(u.id)}
              >
                <div className="chat-list-avatar">
                  <Icon name="user" size={24} />
                </div>
                <div className="chat-list-info">
                  <span className="chat-list-name">
                    {u.display_name || u.first_name}
                    {u.last_name ? ` ${u.last_name}` : ''}
                  </span>
                  {u.username && (
                    <span className="chat-list-preview">@{u.username}</span>
                  )}
                </div>
                <Icon name="message-circle" size={16} className="chat-list-chevron" />
              </button>
            ))
          )}
        </div>
      ) : (
        <>
          <button className="saved-messages-btn fade-in" onClick={handleOpenSaved}>
            <div className="saved-messages-icon">
              <Icon name="heart" size={20} />
            </div>
            <div className="chat-list-info">
              <span className="chat-list-name">Избранное</span>
              <span className="chat-list-preview">Сохранённые сообщения</span>
            </div>
            <Icon name="chevron" size={16} className="chat-list-chevron" />
          </button>

          {loading ? (
            <div className="chat-skeleton">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton-chat-item shimmer" />
              ))}
            </div>
          ) : chats.length === 0 ? (
            <div className="chats-empty">
              Нет чатов. Найдите пользователя через поиск выше.
            </div>
          ) : (
            <ChatList items={chats} onOpenChat={onOpenChat} />
          )}
        </>
      )}
    </div>
  )
}
