import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { onWS } from '@/lib/ws'
import { ChatList } from '@/components/Chat/ChatList'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
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
  onOpenAuthor: (userId: number) => void
}

export function ChatsView({
  onOpenAuthor,
}: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const active = true
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
      setChats(
        data.filter(
          (item) =>
            item.conversation.type !== 'saved',
        ),
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!active) return
    loadChats()
  }, [active, loadChats])

  useEffect(() => {
    if (!active) return
    const offNew = onWS('message.new', () => {
      loadChats()
    })
    const offDeleted = onWS(
      'message.deleted',
      () => {
        loadChats()
      },
    )
    return () => {
      offNew()
      offDeleted()
      if (debounceRef.current)
        clearTimeout(debounceRef.current)
    }
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
    navigate(`/chats/${res.conversation.id}`, {
      state: { title: t('redesign.chats.savedTitle') },
    })
  }

  const handleSelectUser = async (userId: number) => {
    const res = await api.createDM(userId)
    const user = searchResults.find((u) => u.id === userId)
    const name = user
      ? (user.display_name || user.first_name + (user.last_name ? ` ${user.last_name}` : ''))
      : undefined
    setQuery('')
    setSearchResults([])
    navigate(`/chats/${res.conversation.id}`, { state: { title: name } })
  }

  return (
    <div className={`view re-chats-view${active ? ' active' : ''}`}>
      <div className="chats-header">
        <h2 className="chats-title">
          {t('redesign.chats.title')}
        </h2>
        <NotificationBell />
      </div>

      <div className="chats-search-bar">
        <Icon name="search" size={16} className="chats-search-icon" />
        <input
          className="chats-search-input"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder={t('redesign.chats.searchPlaceholder')}
        />
        {query && (
          <MotionPress
            type="button"
            variant="icon"
            className="chats-search-clear"
            ariaLabel={t('redesign.chats.searchClearAria')}
            onClick={() => {
              setQuery('')
              setSearchResults([])
            }}
          >
            <Icon name="x" size={14} />
          </MotionPress>
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
            <div className="chats-empty">
              {t('redesign.chats.emptySearch')}
            </div>
          ) : (
            searchResults.map((u, i) => (
              <div
                key={u.id}
                className="chat-list-item chat-search-item fade-in-stagger"
                style={{ animationDelay: `${i * 50}ms` }}
                onClick={() => onOpenAuthor(u.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onOpenAuthor(u.id)
                  }
                }}
                role="button"
                tabIndex={0}
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
                    <span className="chat-list-preview">
                      @{u.username}
                    </span>
                  )}
                </div>
                <MotionPress
                  type="button"
                  variant="subtle"
                  className="chat-search-message-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    void handleSelectUser(u.id)
                  }}
                >
                  {t('redesign.chats.messageUser')}
                </MotionPress>
              </div>
            ))
          )}
        </div>
      ) : (
        <>
          <MotionPress
            type="button"
            variant="ghost"
            className="saved-messages-btn fade-in"
            onClick={() => void handleOpenSaved()}
          >
            <div className="saved-messages-icon">
              <Icon name="heart" size={20} />
            </div>
            <div className="chat-list-info">
              <span className="chat-list-name">
                {t('redesign.chats.savedTitle')}
              </span>
              <span className="chat-list-preview">
                {t('redesign.chats.savedSubtitle')}
              </span>
            </div>
            <Icon name="chevron" size={16} className="chat-list-chevron" />
          </MotionPress>

          {loading ? (
            <div className="chat-skeleton">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton-chat-item shimmer" />
              ))}
            </div>
          ) : chats.length === 0 ? (
            <div className="chats-empty">
              {t('redesign.chats.emptyChats')}
            </div>
          ) : (
            <ChatList items={chats} />
          )}
        </>
      )}
    </div>
  )
}
