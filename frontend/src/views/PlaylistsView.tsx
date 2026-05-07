import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '@/components/Icon/Icon'
import { LongPressMenu } from '@/components/ui/LongPressMenu'
import { MotionPress } from '@/components/ui/MotionPress'
import { TrackList } from '@/components/TrackList/TrackList'
<<<<<<< HEAD
import { showIsland } from '@/lib/island'
=======
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { useToast } from '@/components/ui/Toast'
import { usePlayerActions } from '@/store/PlayerContext'
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
import { useSound } from '@/store/SoundContext'
import { api } from '@/lib/api'
import {
  getIsAdmin,
  getUserId,
  setBackButton,
} from '@/lib/telegram'
import { usePrefetchTracks } from '@/store/PrefetchContext'
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
  const { t } = useTranslation()
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
  const [renameOpen, setRenameOpen] = useState<Playlist | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [renameBusy, setRenameBusy] = useState(false)
  const uid = getUserId()
  const isAdmin = getIsAdmin()
  const canEditSelected = Boolean(
    selected && uid && (selected.owner_id === uid || isAdmin),
  )

  usePrefetchTracks(
    selected && selected.tracks.length > 0 ? selected.tracks : null,
    'playlist',
  )

  const loadPlaylists = useCallback(() => {
    if (!uid) {
      setPlaylists([])
      return
    }
    setPlaylists(null)
    api.getPlaylists().then(setPlaylists).catch(() => setPlaylists([]))
  }, [uid])

  useEffect(() => {
    loadPlaylists()
<<<<<<< HEAD
  }, [loadPlaylists])
=======
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
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0

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

  const openPlaylist = useCallback(
    async (p: Playlist) => {
      try {
        const detail = await api.getPlaylist(p.id)
        setSelected(detail)
        setScreen('detail')
      } catch {
        showIsland({ kind: 'error', title: t('redesign.library.playlistOpenFail'), durationMs: 3500 })
      }
    },
    [t],
  )

  const handleCreate = useCallback(async () => {
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
  }, [newName, uid, loadPlaylists])

  const refreshSelected = useCallback(async () => {
    if (!selected) return
    const detail = await api.getPlaylist(selected.id)
    setSelected(detail)
  }, [selected])

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

  const beginRename = useCallback((p: Playlist) => {
    setRenameOpen(p)
    setRenameValue(p.name)
  }, [])

  const handleRenameConfirm = useCallback(async () => {
    if (!renameOpen) return
    const trimmed = renameValue.trim()
    if (!trimmed || trimmed === renameOpen.name) {
      setRenameOpen(null)
      return
    }
    setRenameBusy(true)
    try {
      await api.updatePlaylist(renameOpen.id, { name: trimmed })
      loadPlaylists()
      showIsland({
        kind: 'toast',
        title: t('redesign.library.playlistRenameDone'),
        durationMs: 2000,
      })
      setRenameOpen(null)
    } catch {
      showIsland({ kind: 'error', title: t('redesign.library.playlistRenameFail'), durationMs: 3500 })
    } finally {
      setRenameBusy(false)
    }
  }, [renameOpen, renameValue, loadPlaylists, t])

  const handleDuplicate = useCallback(
    async (p: Playlist) => {
      try {
        const detail = await api.getPlaylist(p.id)
        const copyName = t('redesign.library.playlistDuplicateName', {
          name: p.name,
        })
        const created = await api.createPlaylist(
          copyName,
          p.is_public,
        )
        for (const tr of detail.tracks) {
          try {
            await api.addTrackToPlaylist(created.id, tr.id)
          } catch {
            /* skip individual failures */
          }
        }
        loadPlaylists()
        showIsland({
          kind: 'toast',
          title: t('redesign.library.playlistDuplicateDone'),
          durationMs: 2000,
        })
      } catch {
        showIsland({ kind: 'error', title: t('redesign.library.playlistDuplicateFail'), durationMs: 3500 })
      }
    },
    [loadPlaylists, t],
  )

  const handleDelete = useCallback(
    async (p: Playlist) => {
      const ok = window.confirm(
        t('redesign.library.playlistDeleteConfirm', { name: p.name }),
      )
      if (!ok) return
      try {
        await api.deletePlaylist(p.id)
        loadPlaylists()
        showIsland({
          kind: 'toast',
          title: t('redesign.library.playlistDeleteDone'),
          durationMs: 2000,
        })
      } catch {
        showIsland({ kind: 'error', title: t('redesign.library.playlistDeleteFail'), durationMs: 3500 })
      }
    },
    [loadPlaylists, t],
  )

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
<<<<<<< HEAD
    if (item.conversation.type === 'saved') {
      return t('redesign.library.shareChatSaved')
    }
    if (item.conversation.title?.trim()) {
=======
    if (item.conversation.type === 'saved') return 'Избранное'
    if (item.conversation.title?.trim())
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
      return item.conversation.title.trim()
    const peer = item.peer
    const name = peer?.display_name ||
      [peer?.first_name, peer?.last_name].filter(Boolean).join(' ')
    if (name && name.trim()) return name.trim()
    if (peer?.username) return `@${peer.username}`
    return t('redesign.library.shareChatFallback', {
      id: item.conversation.id,
    })
  }

  const loadShareChats = async () => {
    setShareLoading(true)
    setShareError(null)
    try {
      const chats = await api.listChats()
      setShareChats(chats)
    } catch {
      setShareError(
        t('redesign.library.playlistShareLoadFail'),
      )
    } finally {
      setShareLoading(false)
    }
  }

  const openShareModal = async () => {
    if (!selected) return
    setShareOpen(true)
    await loadShareChats()
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
      setShareError(t('redesign.library.shareSendFail'))
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
<<<<<<< HEAD
      showIsland({ kind: 'toast', title: t('redesign.library.shareCopyDone'), durationMs: 2000 })
=======
      toast.success('Ссылка скопирована', { position: 'top' })
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
    } catch {
      showIsland({ kind: 'error', title: t('redesign.library.shareCopyFail'), durationMs: 3500 })
      sound.play('notificationError')
    }
  }

  /* ── Detail screen ──────────────────────────────────────── */
  if (screen === 'detail' && selected) {
    return (
      <section id="view-playlists" className="view active">
        <div className="view-header view-header-detail">
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn back-btn"
            ariaLabel={t('redesign.library.backAria')}
            onClick={() => {
              setScreen('list')
              setSelected(null)
              setShareOpen(false)
            }}
          >
            <Icon
              name="chevron"
              size={20}
              className="back-chevron"
            />
          </MotionPress>
          <div className="rd-pl-detail-meta">
            <h2 className="view-detail-title">{selected.name}</h2>
            <span className="hint">
<<<<<<< HEAD
              {t('redesign.library.playlistTracksCount', {
                count: selected.tracks.length,
              })}
=======
              {selected.tracks.length} треков
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
            </span>
          </div>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn"
<<<<<<< HEAD
            ariaLabel={t('redesign.library.playlistShare')}
            onClick={() => {
              void openShareModal()
            }}
=======
            onClick={() => void openShareModal()}
            aria-label="Поделиться"
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
          >
            <Icon name="share" size={18} />
          </MotionPress>
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
          <div className="rd-pl-edit">
            <div className="form-group">
              <label className="form-label">
                {t('redesign.library.playlistNameLabel')}
              </label>
              <input
                className="form-input"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
<<<<<<< HEAD
            <label className="hint rd-pl-edit-public">
=======
            <label
              className="hint"
              style={{ display: 'block', marginBottom: 12 }}
            >
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
              <input
                type="checkbox"
                checked={editPublic}
                onChange={(e) => setEditPublic(e.target.checked)}
              />
              {t('redesign.library.playlistPublicLabel')}
            </label>
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              onClick={() => void handleSaveMeta()}
              disabled={editBusy}
            >
<<<<<<< HEAD
              {editBusy
                ? t('redesign.library.playlistSaving')
                : t('redesign.library.playlistSave')}
            </MotionPress>
            <div className="rd-pl-add-row">
=======
              {editBusy ? 'Сохранение...' : 'Сохранить'}
            </button>
            <div
              style={{
                display: 'flex',
                gap: 8,
                marginTop: 12,
              }}
            >
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
              <input
                className="form-input rd-pl-add-search"
                placeholder={t(
                  'redesign.library.playlistSearchPlaceholder',
                )}
                value={trackSearch}
                onChange={(e) => setTrackSearch(e.target.value)}
              />
              <select
                className="form-input"
                value={addTrackId ?? ''}
                onChange={(e) =>
                  setAddTrackId(Number(e.target.value) || null)
                }
              >
                <option value="">
                  {t('redesign.library.playlistAddOption')}
                </option>
                {availableTracks.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.title} {tr.artist ? `- ${tr.artist}` : ''}
                  </option>
                ))}
              </select>
<<<<<<< HEAD
              <MotionPress
                type="button"
                variant="ghost"
                haptic="selection"
                className="btn-secondary"
                onClick={() => void handleAddTrack()}
              >
                {t('redesign.library.playlistAdd')}
              </MotionPress>
            </div>
            {searchLoading && (
              <p className="hint rd-pl-search-hint">
                {t('redesign.library.playlistSearching')}
=======
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
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
              </p>
            )}
          </div>
        )}

        {canEditSelected && (
<<<<<<< HEAD
          <div className="rd-pl-edit-rows">
            {selected.tracks.map((tr, idx) => (
              <div key={tr.id} className="rd-pl-edit-row">
                <span className="rd-pl-edit-row-title">{tr.title}</span>
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="selection"
                  className="icon-btn"
                  ariaLabel={t('redesign.library.playlistMoveUp')}
                  onClick={() => void moveTrack(idx, -1)}
                >
                  <Icon name="chevron-up" size={14} />
                </MotionPress>
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="selection"
                  className="icon-btn"
                  ariaLabel={t('redesign.library.playlistMoveDown')}
                  onClick={() => void moveTrack(idx, 1)}
                >
                  <Icon name="chevron-down" size={14} />
                </MotionPress>
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="medium"
                  className="icon-btn"
                  ariaLabel={tr.title}
                  onClick={() => void handleRemoveTrack(tr.id)}
=======
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
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
                >
                  <Icon name="x" size={14} />
                </MotionPress>
              </div>
            ))}
          </div>
        )}

        <TrackList
          tracks={selected.tracks}
          emptyMessage={t('redesign.library.playlistEmptyTracks')}
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
<<<<<<< HEAD
                    {t('redesign.library.shareModalTitle')}
                  </h3>
                  <p className="share-modal-subtitle">{selected.name}</p>
=======
                    Поделиться плейлистом
                  </h3>
                  <p className="share-modal-subtitle">
                    {selected.name}
                  </p>
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
                </div>
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="light"
                  className="icon-btn"
<<<<<<< HEAD
                  ariaLabel={t('redesign.library.playlistCopyLink')}
                  onClick={() => {
                    void handleCopyLink()
                  }}
=======
                  onClick={() => void handleCopyLink()}
                  aria-label="Скопировать ссылку"
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
                >
                  <Icon name="copy" size={16} />
                </MotionPress>
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="light"
                  className="icon-btn"
                  ariaLabel={t('redesign.library.shareClose')}
                  onClick={() => setShareOpen(false)}
                >
                  <Icon name="x" size={18} />
                </MotionPress>
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
                      <MotionPress
                        key={convId}
                        type="button"
                        variant="ghost"
                        haptic="light"
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
                          {sending
                            ? t('redesign.library.shareSending')
                            : t('redesign.library.shareSend')}
                        </span>
                      </MotionPress>
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
          <h2>{t('redesign.library.playlistsTitle')}</h2>
          <span className="hint">
            {t('redesign.library.playlistsSub')}
          </span>
        </div>
      )}

<<<<<<< HEAD
      <MotionPress
        type="button"
        variant="ghost"
        haptic="light"
        className="create-playlist-btn rd-pl-create"
        onClick={() => setCreating(true)}
      >
        <Icon name="plus" size={18} />
        {t('redesign.library.playlistCreate')}
      </MotionPress>
=======
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
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0

      {creating && (
        <div className="rd-pl-create-form">
          <div className="form-group">
            <label className="form-label">
              {t('redesign.library.playlistNameLabel')}
            </label>
            <input
              id="new-playlist-name"
              className="form-input"
              placeholder={t('redesign.library.playlistNamePlaceholder')}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
              autoFocus
            />
          </div>
          <div className="rd-pl-create-actions">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary rd-pl-create-action"
              onClick={() => {
                setCreating(false)
                setNewName('')
              }}
            >
              {t('redesign.library.playlistCancel')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              id="create-playlist-submit"
<<<<<<< HEAD
              className="btn-primary rd-pl-create-action"
              onClick={() => {
                void handleCreate()
              }}
=======
              className="btn-primary"
              style={{ flex: 1, padding: '12px' }}
              onClick={() => void handleCreate()}
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
              disabled={!newName.trim() || loading}
            >
              {loading ? (
                <span className="btn-spinner" />
              ) : (
                t('redesign.library.playlistCreateDo')
              )}
            </MotionPress>
          </div>
        </div>
      )}

      {playlists === null && <div className="loader" />}

<<<<<<< HEAD
      {playlists !== null && playlists.length === 0 && !creating && (
        <div className="empty-hint">
          <strong>{t('redesign.library.playlistsEmpty')}</strong>
          {t('redesign.library.playlistsEmptyHint')}
        </div>
      )}

      {playlists !== null && playlists.length > 0 && (
        <div className="playlist-list rd-playlist-grid">
          {playlists.map((p) => {
            const ownsThis = uid && p.owner_id === uid
            const menuItems = ownsThis
              ? [
                  {
                    id: 'rename',
                    label: t('redesign.library.playlistMenuRename'),
                    icon: 'edit',
                    onPick: () => beginRename(p),
                  },
                  {
                    id: 'duplicate',
                    label: t('redesign.library.playlistMenuDuplicate'),
                    icon: 'copy',
                    onPick: () => {
                      void handleDuplicate(p)
                    },
                  },
                  {
                    id: 'delete',
                    label: t('redesign.library.playlistMenuDelete'),
                    icon: 'trash',
                    destructive: true,
                    onPick: () => {
                      void handleDelete(p)
                    },
                  },
                ]
              : [
                  {
                    id: 'open',
                    label: t('redesign.library.playlistLongOpen'),
                    icon: 'list',
                    onPick: () => {
                      void openPlaylist(p)
                    },
                  },
                ]
            return (
              <LongPressMenu key={p.id} items={menuItems}>
                <div
                  className="playlist-card rd-playlist-card"
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    void openPlaylist(p)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      void openPlaylist(p)
                    }
                  }}
                >
                  <div className="rd-pl-cover">
                    <Icon name="list" size={36} />
                  </div>
                  <div className="rd-pl-info">
                    <div className="rd-pl-name">{p.name}</div>
                    <div className="rd-pl-meta">
                      {p.is_public
                        ? t('redesign.library.playlistPublic')
                        : t('redesign.library.playlistPrivate')}
                      {typeof p.track_count === 'number' && (
                        <>
                          {' · '}
                          {t('redesign.library.playlistTracksCount', {
                            count: p.track_count,
                          })}
                        </>
                      )}
                    </div>
                  </div>
=======
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
>>>>>>> 9aaf5b04bd72da2afa179adfd69dfd1b59c8a5e0
                </div>
              </LongPressMenu>
            )
          })}
        </div>
      )}

      {renameOpen && (
        <div
          className="share-modal-overlay fade-in"
          onClick={(e) => {
            if (e.target === e.currentTarget && !renameBusy) {
              setRenameOpen(null)
            }
          }}
        >
          <div className="share-modal scale-in">
            <div className="share-modal-header">
              <div className="share-modal-title-wrap">
                <h3 className="share-modal-title">
                  {t('redesign.library.playlistRenameTitle')}
                </h3>
              </div>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t('redesign.library.shareClose')}
                disabled={renameBusy}
                onClick={() => setRenameOpen(null)}
              >
                <Icon name="x" size={18} />
              </MotionPress>
            </div>
            <div className="rd-pl-rename-body">
              <input
                className="form-input"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !renameBusy) {
                    void handleRenameConfirm()
                  }
                }}
              />
              <div className="rd-pl-rename-actions">
                <MotionPress
                  type="button"
                  variant="ghost"
                  haptic="light"
                  className="btn-secondary"
                  disabled={renameBusy}
                  onClick={() => setRenameOpen(null)}
                >
                  {t('redesign.library.playlistCancel')}
                </MotionPress>
                <MotionPress
                  type="button"
                  variant="primary"
                  haptic="medium"
                  className="btn-primary"
                  disabled={renameBusy || !renameValue.trim()}
                  onClick={() => {
                    void handleRenameConfirm()
                  }}
                >
                  {renameBusy
                    ? t('redesign.library.playlistSaving')
                    : t('redesign.library.playlistSave')}
                </MotionPress>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
