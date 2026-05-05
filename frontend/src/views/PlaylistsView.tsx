import { useEffect, useMemo, useState } from 'react'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { useToast } from '@/components/ui/Toast'
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
} from '@/types/api'

interface PlaylistsViewProps {
  embedded?: boolean
}

type Screen = 'list' | 'detail'

export function PlaylistsView({
  embedded = false,
}: PlaylistsViewProps) {
  const toast = useToast()
  const sound = useSound()
  const [screen, setScreen] = useState<Screen>('list')
  const [playlists, setPlaylists] = useState<Playlist[] | null>(null)
  const [selected, setSelected] = useState<PlaylistWithTracks | null>(null)
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
    selected &&
    uid &&
    (selected.owner_id === uid || isAdmin),
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
      api.getMyLibrary(1, 100, false).then((res) => {
        setMyTracks(res.items)
      }).catch(() => setMyTracks([]))
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
      api.getTracks({ q, size: 30, page: 1 })
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
    if (item.conversation.type === 'saved') {
      return 'РР·Р±СЂР°РЅРЅРѕРµ'
    }
    if (item.conversation.title?.trim()) {
      return item.conversation.title.trim()
    }
    const peer = item.peer
    const name = peer?.display_name || [peer?.first_name, peer?.last_name]
      .filter(Boolean)
      .join(' ')
    if (name && name.trim()) return name.trim()
    if (peer?.username) return `@${peer.username}`
    return `Р§Р°С‚ #${item.conversation.id}`
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
      setShareError('РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ С‡Р°С‚С‹')
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
      setShareError('РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ')
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
      toast.success('РЎСЃСЃС‹Р»РєР° СЃРєРѕРїРёСЂРѕРІР°РЅР°', {
        position: 'top',
      })
    } catch {
      toast.error('РќРµ СѓРґР°Р»РѕСЃСЊ СЃРєРѕРїРёСЂРѕРІР°С‚СЊ СЃСЃС‹Р»РєСѓ')
      sound.play('notificationError')
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
            aria-label="РќР°Р·Р°Рґ"
          >
            <Icon name="chevron" size={20} className="back-chevron" />
          </button>
          <div>
            <h2 className="view-detail-title">{selected.name}</h2>
            <span className="hint">{selected.tracks.length} С‚СЂРµРєРѕРІ</span>
          </div>
          <button
            type="button"
            className="icon-btn"
            onClick={() => {
              void openShareModal()
            }}
            aria-label="РџРѕРґРµР»РёС‚СЊСЃСЏ"
          >
            <Icon name="share" size={18} />
          </button>
        </div>

        {canEditSelected && (
          <div style={{ padding: '0 16px 16px' }}>
            <div className="form-group">
              <label className="form-label">РќР°Р·РІР°РЅРёРµ</label>
              <input
                className="form-input"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <label className="hint" style={{ display: 'block', marginBottom: 12 }}>
              <input
                type="checkbox"
                checked={editPublic}
                onChange={(e) => setEditPublic(e.target.checked)}
                style={{ marginRight: 8 }}
              />
              РџСѓР±Р»РёС‡РЅС‹Р№
            </label>
            <button
              className="btn-primary"
              onClick={() => {
                void handleSaveMeta()
              }}
              disabled={editBusy}
            >
              {editBusy ? 'РЎРѕС…СЂР°РЅРµРЅРёРµ...' : 'РЎРѕС…СЂР°РЅРёС‚СЊ'}
            </button>
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
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
                onChange={(e) => setAddTrackId(Number(e.target.value) || null)}
              >
                <option value="">Р”РѕР±Р°РІРёС‚СЊ С‚СЂРµРє...</option>
                {availableTracks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} {t.artist ? `- ${t.artist}` : ''}
                  </option>
                ))}
              </select>
              <button className="btn-secondary" onClick={() => void handleAddTrack()}>
                Р”РѕР±Р°РІРёС‚СЊ
              </button>
            </div>
            {searchLoading && (
              <p className="hint" style={{ marginTop: 8 }}>Идёт поиск…</p>
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
                <button className="icon-btn" onClick={() => void moveTrack(idx, -1)}>
                  в†‘
                </button>
                <button className="icon-btn" onClick={() => void moveTrack(idx, 1)}>
                  в†“
                </button>
                <button className="icon-btn" onClick={() => void handleRemoveTrack(t.id)}>
                  <Icon name="x" size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <TrackList
          tracks={selected.tracks}
          emptyMessage="Р’ СЌС‚РѕРј РїР»РµР№Р»РёСЃС‚Рµ РїРѕРєР° РЅРµС‚ С‚СЂРµРєРѕРІ"
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
                  <h3 className="share-modal-title">РџРѕРґРµР»РёС‚СЊСЃСЏ РїР»РµР№Р»РёСЃС‚РѕРј</h3>
                  <p className="share-modal-subtitle">{selected.name}</p>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => {
                    void handleCopyLink()
                  }}
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
                          {sending ? 'РћС‚РїСЂР°РІРєР°...' : 'РћС‚РїСЂР°РІРёС‚СЊ'}
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
          <h2>РџР»РµР№Р»РёСЃС‚С‹</h2>
          <span className="hint">РўРІРѕРё РїРѕРґР±РѕСЂРєРё</span>
        </div>
      )}

      <button
        className="create-playlist-btn"
        onClick={() => setCreating(true)}
      >
        <Icon name="plus" size={18} />
        РЎРѕР·РґР°С‚СЊ РїР»РµР№Р»РёСЃС‚
      </button>

      {creating && (
        <div style={{ padding: '0 16px 16px' }}>
          <div className="form-group">
            <label className="form-label">РќР°Р·РІР°РЅРёРµ РїР»РµР№Р»РёСЃС‚Р°</label>
            <input
              id="new-playlist-name"
              className="form-input"
              placeholder="РњРѕР№ РїР»РµР№Р»РёСЃС‚"
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
              РћС‚РјРµРЅР°
            </button>
            <button
              id="create-playlist-submit"
              className="btn-primary"
              style={{ flex: 1, padding: '12px' }}
              onClick={handleCreate}
              disabled={!newName.trim() || loading}
            >
              {loading ? <span className="btn-spinner" /> : 'РЎРѕР·РґР°С‚СЊ'}
            </button>
          </div>
        </div>
      )}

      {playlists === null && <div className="loader" />}

      {playlists !== null && playlists.length === 0 && !creating && (
        <div className="empty-hint">
          <strong>РџР»РµР№Р»РёСЃС‚РѕРІ РїРѕРєР° РЅРµС‚</strong>
          РЎРѕР·РґР°Р№ СЃРІРѕСЋ РїРµСЂРІСѓСЋ РїРѕРґР±РѕСЂРєСѓ
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
                  {p.is_public ? 'РџСѓР±Р»РёС‡РЅС‹Р№' : 'РџСЂРёРІР°С‚РЅС‹Р№'}
                </div>
              </div>
              <span className="playlist-chevron">вЂє</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

