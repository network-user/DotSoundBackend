import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import {
  getUserId,
  setBackButton,
} from '@/lib/telegram'
import type {
  ChatListItem,
  Playlist,
  PlaylistWithTracks,
} from '@/types/api'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'

interface PlaylistsViewProps {
  embedded?: boolean
}

type Screen = 'list' | 'detail'

export function PlaylistsView({
  embedded = false,
}: PlaylistsViewProps) {
  const [screen, setScreen] = useState<Screen>('list')
  const [playlists, setPlaylists] = useState<Playlist[] | null>(null)
  const [selected, setSelected] =
    useState<PlaylistWithTracks | null>(null)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const [shareChats, setShareChats] = useState<ChatListItem[]>([])
  const [shareLoading, setShareLoading] = useState(false)
  const [shareSendingConvId, setShareSendingConvId] =
    useState<number | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)

  const loadPlaylists = () => {
    const uid = getUserId()
    if (!uid) {
      setPlaylists([])
      return
    }
    setPlaylists(null)
    api
      .getPlaylists()
      .then(setPlaylists)
      .catch(() => setPlaylists([]))
  }

  useEffect(() => {
    loadPlaylists()
  }, [])

  useEffect(() => {
    if (screen !== 'detail') return
    return setBackButton(true, () => {
      setScreen('list')
      setSelected(null)
      setShareOpen(false)
    })
  }, [screen])

  const openPlaylist = async (p: Playlist) => {
    try {
      const detail = await api.getPlaylist(p.id)
      setSelected(detail)
      setScreen('detail')
    } catch {}
  }

  const handleCreate = async () => {
    const uid = getUserId()
    if (!newName.trim() || !uid) return
    setLoading(true)
    try {
      await api.createPlaylist(newName.trim())
      setNewName('')
      setCreating(false)
      loadPlaylists()
    } finally {
      setLoading(false)
    }
  }

  const formatShareChatTitle = (
    item: ChatListItem,
  ): string => {
    if (item.conversation.type === 'saved') {
      return 'Избранное'
    }
    if (item.conversation.title?.trim()) {
      return item.conversation.title.trim()
    }
    const peer = item.peer
    const name = peer?.display_name || [
      peer?.first_name,
      peer?.last_name,
    ]
      .filter(Boolean)
      .join(' ')
    if (name && name.trim()) return name.trim()
    if (peer?.username) return `@${peer.username}`
    return `Чат #${item.conversation.id}`
  }

  const openShareModal = async () => {
    if (!selected) return
    setShareOpen(true)
    setShareLoading(true)
    setShareError(null)
    try {
      const chats = await api.listChats()
      setShareChats(chats)
    } catch {
      setShareError('Не удалось загрузить чаты')
    } finally {
      setShareLoading(false)
    }
  }

  const handleShareToChat = async (
    conversationId: number,
  ) => {
    if (!selected) return
    setShareSendingConvId(conversationId)
    setShareError(null)
    try {
      await api.sendMessage(
        conversationId,
        '',
        {
          type: 'playlist_share',
          shared_playlist_id: selected.id,
        },
      )
      setShareOpen(false)
    } catch {
      setShareError('Не удалось отправить')
    } finally {
      setShareSendingConvId(null)
    }
  }

  if (screen === 'detail' && selected) {
    return (
      <section id="view-playlists" className="view active">
        <div className="view-header view-header-detail">
          <button
            className="icon-btn back-btn"
            onClick={() => {
              setScreen('list')
              setSelected(null)
              setShareOpen(false)
            }}
            aria-label="Назад"
          >
            <Icon name="chevron" size={20} className="back-chevron" />
          </button>
          <div>
            <h2 className="view-detail-title">{selected.name}</h2>
            <span className="hint">
              {selected.tracks.length} треков
            </span>
          </div>
          <button
            type="button"
            className="icon-btn"
            onClick={() => {
              void openShareModal()
            }}
            aria-label="Поделиться"
          >
            <Icon name="share" size={18} />
          </button>
        </div>

        <TrackList
          tracks={selected.tracks}
          emptyMessage="В этом плейлисте пока нет треков"
        />

        {shareOpen && (
          <div
            className="share-modal-overlay fade-in"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setShareOpen(false)
              }
            }}
          >
            <div className="share-modal scale-in">
              <div className="share-modal-header">
                <div className="share-modal-title-wrap">
                  <h3 className="share-modal-title">Поделиться плейлистом</h3>
                  <p className="share-modal-subtitle">{selected.name}</p>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShareOpen(false)}
                  aria-label="Закрыть"
                >
                  <Icon name="x" size={18} />
                </button>
              </div>
              {shareLoading ? (
                <div className="share-modal-loading">
                  <div className="loader" />
                </div>
              ) : (
                <div className="share-chat-list">
                  {shareChats.map((item) => {
                    const convId = item.conversation.id
                    const sending = shareSendingConvId === convId
                    return (
                      <button
                        key={convId}
                        type="button"
                        className="share-chat-row"
                        onClick={() => {
                          void handleShareToChat(convId)
                        }}
                        disabled={shareSendingConvId !== null}
                      >
                        <span className="share-chat-icon">
                          <Icon
                            name={
                              item.conversation.type === 'group'
                                ? 'users-following'
                                : item.conversation.type === 'saved'
                                  ? 'heart'
                                  : 'user'
                            }
                            size={16}
                          />
                        </span>
                        <span className="share-chat-meta">
                          <span className="share-chat-title">
                            {formatShareChatTitle(item)}
                          </span>
                        </span>
                        <span className="share-chat-action">
                          {sending ? 'Отправка…' : 'Отправить'}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
              {shareError && (
                <div className="share-modal-error">{shareError}</div>
              )}
            </div>
          </div>
        )}
      </section>
    )
  }

  return (
    <section id="view-playlists" className="view active">
      {!embedded && (
        <div className="view-header">
          <h2>Плейлисты</h2>
          <span className="hint">Твои подборки</span>
        </div>
      )}

      <button
        className="create-playlist-btn"
        onClick={() => setCreating(true)}
      >
        <Icon name="plus" size={18} />
        Создать плейлист
      </button>

      {creating && (
        <div style={{ padding: '0 16px 16px' }}>
          <div className="form-group">
            <label className="form-label">Название плейлиста</label>
            <input
              id="new-playlist-name"
              className="form-input"
              placeholder="Мой плейлист"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              autoFocus
            />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="btn-secondary"
              style={{ flex: 1 }}
              onClick={() => {
                setCreating(false)
                setNewName('')
              }}
            >
              Отмена
            </button>
            <button
              id="create-playlist-submit"
              className="btn-primary"
              style={{ flex: 1, padding: '12px' }}
              onClick={handleCreate}
              disabled={!newName.trim() || loading}
            >
              {loading ? <span className="btn-spinner" /> : 'Создать'}
            </button>
          </div>
        </div>
      )}

      {playlists === null && <div className="loader" />}

      {playlists !== null && playlists.length === 0 && !creating && (
        <div className="empty-hint">
          <strong>Плейлистов пока нет</strong>
          Создай свою первую подборку
        </div>
      )}

      {playlists !== null && playlists.length > 0 && (
        <div className="playlist-list">
          {playlists.map((p) => (
            <div
              key={p.id}
              className="playlist-card"
              onClick={() => {
                void openPlaylist(p)
              }}
            >
              <div className="playlist-cover">
                <Icon name="list" size={20} />
              </div>
              <div className="playlist-info">
                <div className="playlist-name">{p.name}</div>
                <div className="playlist-meta">
                  {p.is_public ? 'Публичный' : 'Приватный'}
                </div>
              </div>
              <span className="playlist-chevron">›</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
