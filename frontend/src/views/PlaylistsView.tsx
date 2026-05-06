import { useEffect, useMemo, useState } from 'react'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { useToast } from '@/components/ui/Toast'
import { usePlayerActions } from '@/store/PlayerContext'
import { useSound } from '@/store/SoundContext'
import { api } from '@/lib/api'
import {
  getIsAdmin,
  getUserId,
  setBackButton,
} from '@/lib/telegram'
import type {
  ChatListItem,
  Playlist,
  PlaylistWithTracks,
  Track,
  WeeklyTopPlaylistResponse,
  GenreMixesResponse,
} from '@/types/api'

interface PlaylistsViewProps {
  embedded?: boolean
  onNavigate?: (path: string) => void
}

type Screen = 'list' | 'detail'

const AUTO_TYPE_LABELS: Record<string, string> = {
  auto_weekly_top: 'Топ недели',
  auto_genre_mix: 'Жанровый микс',
  auto_daily_mix: 'Дневной микс',
  editorial: 'Редакционный',
  imported_sc: 'Из SoundCloud',
  imported_bc: 'Из Bandcamp',
}

function PlaylistCover({
  playlist,
  size = 56,
}: {
  playlist: Playlist | { cover_key?: string | null; name: string }
  size?: number
}) {
  const coverKey = 'cover_key' in playlist ? playlist.cover_key : null
  if (coverKey) {
    return (
      <CoverImage
        coverKey={coverKey}
        className="playlist-cover-img"
        style={{ width: size, height: size }}
      />
    )
  }
  return (
    <div
      className="playlist-cover"
      style={{ width: size, height: size }}
    >
      <Icon name="list" size={size * 0.36} />
    </div>
  )
}

function formatPlaylistMeta(p: Playlist): string {
  if (AUTO_TYPE_LABELS[p.playlist_type]) {
    return AUTO_TYPE_LABELS[p.playlist_type]
  }
  return p.is_public ? 'Публичный' : 'Приватный'
}

export function PlaylistsView({
  embedded = false,
  onNavigate,
}: PlaylistsViewProps) {
  const toast = useToast()
  const sound = useSound()
  const { playTrack } = usePlayerActions()
  const [screen, setScreen] = useState<Screen>('list')
  const [playlists, setPlaylists] = useState<Playlist[] | null>(null)
  const [featuredPlaylists, setFeaturedPlaylists] = useState<
    PlaylistWithTracks[]
  >([])
  const [weeklyTop, setWeeklyTop] =
    useState<WeeklyTopPlaylistResponse | null>(null)
  const [genreMixes, setGenreMixes] =
    useState<GenreMixesResponse | null>(null)
  const [selected, setSelected] = useState<PlaylistWithTracks | null>(
    null,
  )
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const [shareChats, setShareChats] = useState<ChatListItem[]>([])
  const [shareLoading, setShareLoading] = useState(false)
  const [shareSendingConvId, setShareSendingConvId] =
    useState<number | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editPublic, setEditPublic] = useState(false)
  const [editBusy, setEditBusy] = useState(false)
  const [myTracks, setMyTracks] = useState<Track[]>([])
  const [addTrackId, setAddTrackId] = useState<number | null>(null)
  const [trackSearch, setTrackSearch] = useState('')
  const [searchResults, setSearchResults] = useState<Track[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const uid = getUserId()
  const isAdmin = getIsAdmin()
  const canEditSelected = Boolean(
    selected && uid && (selected.owner_id === uid || isAdmin),
  )

  const loadPlaylists = () => {
    if (!uid) {
      setPlaylists([])
      return
    }
    setPlaylists(null)
    api.getPlaylists().then(setPlaylists).catch(() => setPlaylists([]))
  }

  useEffect(() => {
    loadPlaylists()
    api
      .getFeaturedPlaylists(6)
      .then(setFeaturedPlaylists)
      .catch(() => setFeaturedPlaylists([]))
    api
      .getWeeklyTopPlaylist()
      .then(setWeeklyTop)
      .catch(() => setWeeklyTop(null))
    api
      .getGenreMixes()
      .then(setGenreMixes)
      .catch(() => setGenreMixes(null))
  }, [])

  useEffect(() => {
    if (screen !== 'detail') return
    return setBackButton(true, () => {
      setScreen('list')
      setSelected(null)
      setShareOpen(false)
    })
  }, [screen])

  useEffect(() => {
    if (!selected) return
    setEditName(selected.name)
    setEditPublic(selected.is_public)
    if (canEditSelected) {
      api
        .getMyLibrary(1, 100, false)
        .then((res) => setMyTracks(res.items))
        .catch(() => setMyTracks([]))
    }
  }, [selected?.id, canEditSelected])

  useEffect(() => {
    if (!selected || !canEditSelected) return
    const q = trackSearch.trim()
    if (!q) {
      setSearchResults([])
      setSearchLoading(false)
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      setSearchLoading(true)
      api
        .getTracks({ q, size: 30, page: 1 })
        .then((res) => {
          if (cancelled) return
          setSearchResults(res.items)
        })
        .catch(() => {
          if (cancelled) return
          setSearchResults([])
        })
        .finally(() => {
          if (!cancelled) setSearchLoading(false)
        })
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [selected?.id, canEditSelected, trackSearch])

  const openPlaylist = async (p: Playlist) => {
    try {
      const detail = await api.getPlaylist(p.id)
      setSelected(detail)
      setScreen('detail')
    } catch {}
  }

  const handleCreate = async () => {
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

  const refreshSelected = async () => {
    if (!selected) return
    const detail = await api.getPlaylist(selected.id)
    setSelected(detail)
  }

  const handleSaveMeta = async () => {
    if (!selected || !canEditSelected) return
    setEditBusy(true)
    try {
      await api.updatePlaylist(selected.id, {
        name: editName.trim() || selected.name,
        is_public: editPublic,
      })
      await refreshSelected()
      loadPlaylists()
    } finally {
      setEditBusy(false)
    }
  }

  const handleRemoveTrack = async (trackId: number) => {
    if (!selected || !canEditSelected) return
    await api.removeTrackFromPlaylist(selected.id, trackId)
    await refreshSelected()
  }

  const handleAddTrack = async () => {
    if (!selected || !canEditSelected || !addTrackId) return
    await api.addTrackToPlaylist(selected.id, addTrackId)
    await refreshSelected()
    setAddTrackId(null)
  }

  const moveTrack = async (index: number, dir: -1 | 1) => {
    if (!selected || !canEditSelected) return
    const nextIndex = index + dir
    if (nextIndex < 0 || nextIndex >= selected.tracks.length) return
    const ids = selected.tracks.map((t) => t.id)
    const tmp = ids[index]
    ids[index] = ids[nextIndex]
    ids[nextIndex] = tmp
    await api.setPlaylistTrackOrder(selected.id, ids)
    await refreshSelected()
  }

  const availableTracks = useMemo(() => {
    if (!selected) return []
    const inPlaylist = new Set(selected.tracks.map((t) => t.id))
    const local = myTracks.filter((t) => !inPlaylist.has(t.id))
    const q = trackSearch.trim().toLowerCase()
    const base = q
      ? local.filter((t) => {
          const hay = `${t.title} ${t.artist ?? ''}`.toLowerCase()
          return hay.includes(q)
        })
      : local
    const merged = [...base]
    for (const remote of searchResults) {
      if (
        !inPlaylist.has(remote.id) &&
        !merged.some((t) => t.id === remote.id)
      ) {
        merged.push(remote)
      }
    }
    return merged
  }, [selected, myTracks, trackSearch, searchResults])

  const formatShareChatTitle = (item: ChatListItem): string => {
    if (item.conversation.type === 'saved') return 'Избранное'
    if (item.conversation.title?.trim())
      return item.conversation.title.trim()
    const peer = item.peer
    const name = peer?.display_name ||
      [peer?.first_name, peer?.last_name].filter(Boolean).join(' ')
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

  const handleShareToChat = async (conversationId: number) => {
    if (!selected) return
    setShareSendingConvId(conversationId)
    setShareError(null)
    try {
      await api.sendMessage(conversationId, '', {
        type: 'playlist_share',
        shared_playlist_id: selected.id,
      })
      setShareOpen(false)
    } catch {
      setShareError('Не удалось отправить')
    } finally {
      setShareSendingConvId(null)
    }
  }

  const handleCopyLink = async () => {
    if (!selected) return
    const url = `${window.location.origin}${import.meta.env.BASE_URL}playlists`
    try {
      await navigator.clipboard.writeText(url)
      sound.play('notificationInfo')
      toast.success('Ссылка скопирована', { position: 'top' })
    } catch {
      toast.error('Не удалось скопировать ссылку')
      sound.play('notificationError')
    }
  }

  /* ── Detail screen ──────────────────────────────────────── */
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
            onClick={() => void openShareModal()}
            aria-label="Поделиться"
          >
            <Icon name="share" size={18} />
          </button>
        </div>

        {selected.description && (
          <p
            style={{
              padding: '0 16px 12px',
              color: 'var(--text-secondary)',
              fontSize: 13,
            }}
          >
            {selected.description}
          </p>
        )}

        {canEditSelected && (
          <div style={{ padding: '0 16px 16px' }}>
            <div className="form-group">
              <label className="form-label">Название</label>
              <input
                className="form-input"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <label
              className="hint"
              style={{ display: 'block', marginBottom: 12 }}
            >
              <input
                type="checkbox"
                checked={editPublic}
                onChange={(e) => setEditPublic(e.target.checked)}
                style={{ marginRight: 8 }}
              />
              Публичный
            </label>
            <button
              className="btn-primary"
              onClick={() => void handleSaveMeta()}
              disabled={editBusy}
            >
              {editBusy ? 'Сохранение...' : 'Сохранить'}
            </button>
            <div
              style={{
                display: 'flex',
                gap: 8,
                marginTop: 12,
              }}
            >
              <input
                className="form-input"
                placeholder="Поиск треков: название или артист..."
                value={trackSearch}
                onChange={(e) => setTrackSearch(e.target.value)}
                style={{ minWidth: 220 }}
              />
              <select
                className="form-input"
                value={addTrackId ?? ''}
                onChange={(e) =>
                  setAddTrackId(Number(e.target.value) || null)
                }
              >
                <option value="">Добавить трек...</option>
                {availableTracks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} {t.artist ? `- ${t.artist}` : ''}
                  </option>
                ))}
              </select>
              <button
                className="btn-secondary"
                onClick={() => void handleAddTrack()}
              >
                Добавить
              </button>
            </div>
            {searchLoading && (
              <p className="hint" style={{ marginTop: 8 }}>
                Идёт поиск…
              </p>
            )}
          </div>
        )}

        {canEditSelected && (
          <div style={{ padding: '0 16px 16px' }}>
            {selected.tracks.map((t, idx) => (
              <div
                key={t.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 8,
                }}
              >
                <span style={{ flex: 1 }}>{t.title}</span>
                <button
                  className="icon-btn"
                  onClick={() => void moveTrack(idx, -1)}
                >
                  ↑
                </button>
                <button
                  className="icon-btn"
                  onClick={() => void moveTrack(idx, 1)}
                >
                  ↓
                </button>
                <button
                  className="icon-btn"
                  onClick={() => void handleRemoveTrack(t.id)}
                >
                  <Icon name="x" size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <TrackList
          tracks={selected.tracks}
          emptyMessage="В этом плейлисте пока нет треков"
        />

        {shareOpen && (
          <div
            className="share-modal-overlay fade-in"
            onClick={(e) => {
              if (e.target === e.currentTarget) setShareOpen(false)
            }}
          >
            <div className="share-modal scale-in">
              <div className="share-modal-header">
                <div className="share-modal-title-wrap">
                  <h3 className="share-modal-title">
                    Поделиться плейлистом
                  </h3>
                  <p className="share-modal-subtitle">
                    {selected.name}
                  </p>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => void handleCopyLink()}
                  aria-label="Скопировать ссылку"
                >
                  <Icon name="copy" size={16} />
                </button>
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
                        onClick={() =>
                          void handleShareToChat(convId)
                        }
                        disabled={shareSendingConvId !== null}
                      >
                        <span className="share-chat-icon">
                          <Icon
                            name={
                              item.conversation.type === 'group'
                                ? 'users-following'
                                : item.conversation.type ===
                                    'saved'
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
                          {sending ? 'Отправка...' : 'Отправить'}
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

  /* ── List screen ────────────────────────────────────────── */
  const userPlaylists = (playlists ?? []).filter(
    (p) => p.playlist_type === 'user',
  )
  const autoPlaylists = (playlists ?? []).filter(
    (p) => p.playlist_type !== 'user',
  )

  return (
    <section id="view-playlists" className="view active">
      {!embedded && (
        <div className="view-header">
          <h2>Плейлисты</h2>
          <span className="hint">Твои подборки</span>
        </div>
      )}

      {/* ── Featured / Editorial section ─────────────────── */}
      {featuredPlaylists.length > 0 && (
        <div className="playlists-featured-section">
          <p className="search-section-label" style={{ padding: '0 16px 10px' }}>
            Рекомендованные
          </p>
          <div className="playlists-featured-scroll">
            {featuredPlaylists.map((p) => (
              <button
                key={p.id}
                type="button"
                className="playlist-featured-card"
                onClick={() => void openPlaylist(p)}
              >
                <div className="playlist-featured-cover">
                  {p.cover_key ? (
                    <CoverImage coverKey={p.cover_key} />
                  ) : (
                    <Icon name="list" size={24} />
                  )}
                </div>
                <div className="playlist-featured-info">
                  <p className="playlist-featured-name">{p.name}</p>
                  {p.description && (
                    <p className="playlist-featured-desc">
                      {p.description}
                    </p>
                  )}
                  <p className="playlist-featured-meta">
                    {p.tracks.length} треков
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Auto-generated playlists ─────────────────────── */}
      <div className="playlists-auto-section">
        {weeklyTop && weeklyTop.tracks.length > 0 && (
          <button
            type="button"
            className="playlist-auto-card"
            onClick={() =>
              onNavigate?.('/weekly-top')
            }
          >
            <div className="playlist-auto-icon">
              <Icon name="fire" size={22} />
            </div>
            <div className="playlist-auto-info">
              <p className="playlist-auto-name">Топ недели</p>
              <p className="playlist-auto-meta">
                {weeklyTop.tracks.length} треков
              </p>
            </div>
            <Icon
              name="chevron"
              size={16}
              className="playlist-auto-chevron"
            />
          </button>
        )}

        {genreMixes && genreMixes.mixes.length > 0 && (
          <>
            <p
              className="search-section-label"
              style={{
                padding: '16px 16px 8px',
                display: 'block',
              }}
            >
              Жанровые миксы
            </p>
            {genreMixes.mixes.map((mix) => (
              <button
                key={mix.genre}
                type="button"
                className="playlist-auto-card"
                onClick={() =>
                  onNavigate?.(`/genre-mix/${mix.genre}`)
                }
              >
                <div className="playlist-auto-icon">
                  <Icon name="music-note" size={20} />
                </div>
                <div className="playlist-auto-info">
                  <p className="playlist-auto-name">{mix.title}</p>
                  <p className="playlist-auto-meta">
                    {mix.tracks.length} треков
                  </p>
                </div>
                <Icon
                  name="chevron"
                  size={16}
                  className="playlist-auto-chevron"
                />
              </button>
            ))}
          </>
        )}

        {autoPlaylists.length > 0 && (
          <>
            {autoPlaylists.map((p) => (
              <button
                key={p.id}
                type="button"
                className="playlist-auto-card"
                onClick={() => void openPlaylist(p)}
              >
                <PlaylistCover playlist={p} size={44} />
                <div className="playlist-auto-info">
                  <p className="playlist-auto-name">{p.name}</p>
                  <p className="playlist-auto-meta">
                    {formatPlaylistMeta(p)}
                  </p>
                </div>
                <Icon
                  name="chevron"
                  size={16}
                  className="playlist-auto-chevron"
                />
              </button>
            ))}
          </>
        )}
      </div>

      {/* ── User playlists ────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 16px 8px',
        }}
      >
        <p className="search-section-label" style={{ padding: 0 }}>
          Мои плейлисты
        </p>
        <button
          className="playlist-create-inline"
          onClick={() => setCreating(true)}
          type="button"
        >
          <Icon name="plus" size={16} />
          Создать
        </button>
      </div>

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
              onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
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
              onClick={() => void handleCreate()}
              disabled={!newName.trim() || loading}
            >
              {loading ? <span className="btn-spinner" /> : 'Создать'}
            </button>
          </div>
        </div>
      )}

      {playlists === null && <div className="loader" />}

      {playlists !== null &&
        userPlaylists.length === 0 &&
        !creating && (
          <div className="empty-hint" style={{ padding: '12px 16px' }}>
            Создай свою первую подборку
          </div>
        )}

      {userPlaylists.length > 0 && (
        <div className="playlist-list">
          {userPlaylists.map((p) => (
            <div
              key={p.id}
              className="playlist-card"
              onClick={() => void openPlaylist(p)}
            >
              <PlaylistCover playlist={p} size={48} />
              <div className="playlist-info">
                <div className="playlist-name">{p.name}</div>
                <div className="playlist-meta">
                  {formatPlaylistMeta(p)}
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
