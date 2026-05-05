import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import { usePlayerActions } from '@/store/PlayerContext'
import type {
  ChatListItem,
  Track,
} from '@/types/api'

export function GenreMixView() {
  const { genre } = useParams<{ genre: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const { playTrack } = usePlayerActions()

  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [title, setTitle] = useState<string>(
    genre
      ? `Mix: ${genre.charAt(0).toUpperCase()}${genre.slice(1)}`
      : 'Жанровый микс',
  )
  const [shareOpen, setShareOpen] = useState(false)
  const [shareChats, setShareChats] = useState<ChatListItem[]>([])
  const [shareLoading, setShareLoading] = useState(false)
  const [shareSendingConvId, setShareSendingConvId] = useState<number | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [isAdmin, setIsAdmin] = useState(() => getIsAdmin())
  const [debugMode, setDebugMode] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const [trackPool, setTrackPool] = useState<Track[]>([])
  const [addTrackId, setAddTrackId] = useState<number | null>(null)

  const canEditUi = isAdmin || debugMode || import.meta.env.DEV

  const shareUrl = `${window.location.origin}${import.meta.env.BASE_URL}genre-mix/${encodeURIComponent(
    genre || '',
  )}`

  useEffect(() => {
    let cancelled = false
    api.syncSessionUserFlags().finally(() => {
      if (!cancelled) {
        setIsAdmin(getIsAdmin())
      }
    })
    api.getAuthConfig()
      .then((cfg) => {
        if (!cancelled) {
          setDebugMode(Boolean(cfg.debug))
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!genre) return
    api
      .getGenreMixes()
      .then((data) => {
        const mix = data.mixes.find(
          (m) => m.genre.toLowerCase() === genre.toLowerCase(),
        )
        if (mix) {
          setTracks(mix.tracks)
          setTitle(mix.title)
        } else {
          setTracks([])
        }
      })
      .catch(() => setTracks([]))
  }, [genre])

  const handlePlayAll = useCallback(async () => {
    if (!tracks || !tracks.length) return
    await playTrack(tracks[0])
  }, [tracks, playTrack])

  const formatShareChatTitle = useCallback((item: ChatListItem): string => {
    if (item.conversation.type === 'saved') return 'Избранное'
    if (item.conversation.title?.trim()) return item.conversation.title.trim()
    const peer = item.peer
    const name = peer?.display_name || [peer?.first_name, peer?.last_name]
      .filter(Boolean)
      .join(' ')
    if (name && name.trim()) return name.trim()
    if (peer?.username) return `@${peer.username}`
    return `Чат #${item.conversation.id}`
  }, [])

  const openShareModal = useCallback(async () => {
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
  }, [])

  const handleShareToChat = useCallback(async (conversationId: number) => {
    setShareSendingConvId(conversationId)
    setShareError(null)
    try {
      await api.sendMessage(conversationId, shareUrl)
      setShareOpen(false)
      toast.success('Ссылка отправлена')
    } catch {
      setShareError('Не удалось отправить')
    } finally {
      setShareSendingConvId(null)
    }
  }, [shareUrl, toast])

  const handleCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      toast.success('Ссылка скопирована', {
        position: 'top',
      })
    } catch {
      setShareError('Не удалось скопировать ссылку')
    }
  }, [shareUrl, toast])

  const openEditMode = useCallback(async () => {
    if (!canEditUi) return
    setTitleDraft(title)
    setEditOpen(true)
    try {
      const lib = await api.getMyLibrary(1, 100, false)
      setTrackPool(lib.items)
    } catch {
      setTrackPool([])
    }
  }, [canEditUi, title])

  const moveTrack = useCallback((index: number, dir: -1 | 1) => {
    setTracks((prev) => {
      if (!prev) return prev
      const next = [...prev]
      const to = index + dir
      if (to < 0 || to >= next.length) return prev
      const tmp = next[index]
      next[index] = next[to]
      next[to] = tmp
      return next
    })
  }, [])

  const removeTrack = useCallback((trackId: number) => {
    setTracks((prev) => (prev ? prev.filter((t) => t.id !== trackId) : prev))
  }, [])

  const addTrack = useCallback(() => {
    if (!addTrackId) return
    const candidate = trackPool.find((t) => t.id === addTrackId)
    if (!candidate) return
    setTracks((prev) => {
      if (!prev) return [candidate]
      if (prev.some((t) => t.id === candidate.id)) return prev
      return [...prev, candidate]
    })
    setAddTrackId(null)
  }, [addTrackId, trackPool])

  return (
    <section className="view active">
      <div className="view-header">
        <button className="icon-btn" onClick={() => navigate(-1)} aria-label="Назад">
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div style={{ flex: 1 }}>
          <h2>{title}</h2>
          {tracks !== null && <span className="hint">{tracks.length} треков</span>}
        </div>
        {tracks && tracks.length > 0 && (
          <div style={{ display: 'flex', gap: 8 }}>
            {canEditUi && (
              <button className="icon-btn" onClick={() => { void openEditMode() }} aria-label="Редактировать микс">
                <Icon name="edit" size={18} />
              </button>
            )}
            <button className="icon-btn" onClick={() => { void openShareModal() }} aria-label="Поделиться">
              <Icon name="share" size={18} />
            </button>
            <button className="icon-btn" onClick={handlePlayAll} aria-label="Слушать всё">
              <Icon name="play" size={20} />
            </button>
          </div>
        )}
      </div>

      <TrackList tracks={tracks} emptyMessage="В этом миксе пока нет треков" />

      {editOpen && (
        <div className="share-modal-overlay fade-in" onClick={(e) => {
          if (e.target === e.currentTarget) setEditOpen(false)
        }}>
          <div className="share-modal scale-in gm-edit-modal">
            <div className="share-modal-header">
              <div className="share-modal-title-wrap">
                <h3 className="share-modal-title">Редактирование микса</h3>
                <p className="share-modal-subtitle">Debug/Dev режим</p>
              </div>
              <button type="button" className="icon-btn" onClick={() => setEditOpen(false)} aria-label="Закрыть">
                <Icon name="x" size={18} />
              </button>
            </div>
            <div className="form-group gm-edit-section">
              <label className="form-label">Название</label>
              <input
                className="form-input gm-edit-input"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
              />
              <button
                type="button"
                className="btn-primary gm-edit-btn"
                onClick={() => {
                  setTitle(titleDraft.trim() || title)
                  toast.success('Название обновлено', { position: 'top' })
                }}
              >
                Применить
              </button>
            </div>
            <div className="gm-edit-add-row">
              <select
                className="form-input gm-edit-input"
                value={addTrackId ?? ''}
                onChange={(e) => setAddTrackId(Number(e.target.value) || null)}
              >
                <option value="">Добавить трек...</option>
                {trackPool
                  .filter((t) => !(tracks ?? []).some((mt) => mt.id === t.id))
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title} {t.artist ? `- ${t.artist}` : ''}
                    </option>
                  ))}
              </select>
              <button type="button" className="btn-secondary gm-edit-btn" onClick={addTrack}>
                Добавить
              </button>
            </div>
            <div className="gm-edit-list">
              {(tracks ?? []).map((t, idx) => (
                <div key={t.id} className="gm-edit-item">
                  <div className="gm-edit-item-main">
                    <span className="gm-edit-item-title">{t.title}</span>
                    <span className="gm-edit-item-artist">{t.artist || '—'}</span>
                  </div>
                  <div className="gm-edit-item-actions">
                    <button type="button" className="icon-btn gm-edit-icon-btn" onClick={() => moveTrack(idx, -1)}>↑</button>
                    <button type="button" className="icon-btn gm-edit-icon-btn" onClick={() => moveTrack(idx, 1)}>↓</button>
                    <button type="button" className="icon-btn gm-edit-icon-btn" onClick={() => removeTrack(t.id)}>
                    <Icon name="x" size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {shareOpen && (
        <div className="share-modal-overlay fade-in" onClick={(e) => {
          if (e.target === e.currentTarget) setShareOpen(false)
        }}>
          <div className="share-modal scale-in">
            <div className="share-modal-header">
              <div className="share-modal-title-wrap">
                <h3 className="share-modal-title">Поделиться миксом</h3>
                <p className="share-modal-subtitle">{title}</p>
              </div>
              <button type="button" className="icon-btn" onClick={() => { void handleCopyLink() }} aria-label="Скопировать ссылку">
                <Icon name="copy" size={16} />
              </button>
              <button type="button" className="icon-btn" onClick={() => setShareOpen(false)} aria-label="Закрыть">
                <Icon name="x" size={18} />
              </button>
            </div>
            {shareLoading ? (
              <div className="share-modal-loading"><div className="loader" /></div>
            ) : (
              <div className="share-chat-list">
                {shareChats.map((item) => {
                  const convId = item.conversation.id
                  const sending = shareSendingConvId === convId
                  return (
                    <button key={convId} type="button" className="share-chat-row" onClick={() => { void handleShareToChat(convId) }} disabled={shareSendingConvId !== null}>
                      <span className="share-chat-icon">
                        <Icon name={item.conversation.type === 'group' ? 'users-following' : item.conversation.type === 'saved' ? 'heart' : 'user'} size={16} />
                      </span>
                      <span className="share-chat-meta"><span className="share-chat-title">{formatShareChatTitle(item)}</span></span>
                      <span className="share-chat-action">{sending ? 'Отправка...' : 'Отправить'}</span>
                    </button>
                  )
                })}
              </div>
            )}
            {shareError && <div className="share-modal-error">{shareError}</div>}
          </div>
        </div>
      )}
    </section>
  )
}
