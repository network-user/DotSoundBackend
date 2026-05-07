import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { showIsland } from '@/lib/island'
import { useSound } from '@/store/SoundContext'
import { api, getApiErrorMessage } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import { VARIANTS_FADE_UP, m } from '@/lib/motion'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import type {
  ChatListItem,
  Track,
} from '@/types/api'

export function GenreMixView() {
  const { t } = useTranslation()
  const { genre } = useParams<{ genre: string }>()
  const navigate = useNavigate()
  const { playTrack, toggleShuffle } = usePlayerActions()
  const { shuffleOn } = usePlayerMeta()
  const sound = useSound()

  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [title, setTitle] = useState<string>(
    genre
      ? `Mix: ${genre.charAt(0).toUpperCase()}${genre.slice(1)}`
      : t('redesign.home.sectionGenreMixes', 'Жанровый микс'),
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
  const [saveBusy, setSaveBusy] = useState(false)
  const [trackSearch, setTrackSearch] = useState('')
  const [searchResults, setSearchResults] = useState<Track[]>([])
  const [searchLoading, setSearchLoading] = useState(false)

  const canEditUi = isAdmin || debugMode || import.meta.env.DEV
  const normalizedGenre = (genre || '').toLowerCase()

  usePrefetchTracks(tracks ?? null, 'genre_mix')

  const shareUrl = `${window.location.origin}${import.meta.env.BASE_URL}genre-mix/${encodeURIComponent(
    genre || '',
  )}`

  function mixCoverUrl(key: string | null): string | null {
    if (!key) return null
    return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
  }

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
      .getGenreMix(genre)
      .then((mix) => {
        setTracks(mix.tracks)
        setTitle(mix.title)
      })
      .catch(() => setTracks([]))
  }, [genre])

  useEffect(() => {
    if (!editOpen || !canEditUi) return
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
          if (!cancelled) {
            setSearchResults(res.items)
          }
        })
        .catch(() => {
          if (!cancelled) {
            setSearchResults([])
          }
        })
        .finally(() => {
          if (!cancelled) {
            setSearchLoading(false)
          }
        })
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [editOpen, canEditUi, trackSearch])

  const handlePlayAll = useCallback(async () => {
    if (!tracks || !tracks.length) return
    await playTrack(tracks[0])
  }, [tracks, playTrack])

  const handleShufflePlay = useCallback(async () => {
    if (!tracks || !tracks.length) return
    try {
      if (!shuffleOn) toggleShuffle()
      const pick =
        tracks[Math.floor(Math.random() * tracks.length)]
      await playTrack(pick)
    } catch (e) {
      showIsland({ kind: 'error', title: getApiErrorMessage(e, t('redesign.artist.playError')), durationMs: 4000 })
    }
  }, [tracks, playTrack, shuffleOn, toggleShuffle, t])

  const formatShareChatTitle = useCallback(
    (item: ChatListItem): string => {
      if (item.conversation.type === 'saved') {
        return t('redesign.library.shareSaved', 'Избранное')
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
      return t('redesign.library.shareChatNumber', {
        id: item.conversation.id,
        defaultValue: `Чат #${item.conversation.id}`,
      })
    },
    [t],
  )

  const openShareModal = useCallback(async () => {
    setShareOpen(true)
    setShareLoading(true)
    setShareError(null)
    try {
      const chats = await api.listChats()
      setShareChats(chats)
    } catch {
      setShareError(
        t('redesign.library.shareLoadFail', 'Не удалось загрузить чаты'),
      )
    } finally {
      setShareLoading(false)
    }
  }, [t])

  const handleShareToChat = useCallback(
    async (conversationId: number) => {
      setShareSendingConvId(conversationId)
      setShareError(null)
      try {
        await api.sendMessage(conversationId, shareUrl)
        setShareOpen(false)
        sound.play('notificationSuccess')
        showIsland({
          kind: 'toast',
          title: t('redesign.library.shareLinkSent', 'Ссылка отправлена'),
          durationMs: 2200,
        })
      } catch {
        setShareError(
          t('redesign.library.shareLinkSendFail', 'Не удалось отправить'),
        )
        sound.play('notificationError')
      } finally {
        setShareSendingConvId(null)
      }
    },
    [shareUrl, sound, t],
  )

  const handleCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      sound.play('notificationInfo')
      showIsland({
        kind: 'toast',
        title: t('redesign.library.shareLinkCopied', 'Ссылка скопирована'),
        durationMs: 2000,
      })
    } catch {
      setShareError(
        t('redesign.library.shareLinkCopyFail', 'Не удалось скопировать ссылку'),
      )
      sound.play('notificationError')
    }
  }, [shareUrl, sound, t])

  const persistOverride = useCallback(
    async (nextTitle: string, nextTracks: Track[]) => {
      if (!normalizedGenre || !canEditUi) return
      setSaveBusy(true)
      try {
        const saved = await api.saveGenreMixOverride(
          normalizedGenre,
          {
            title: nextTitle,
            track_ids: nextTracks.map((tr) => tr.id),
          },
        )
        setTitle(saved.title)
        setTracks(saved.tracks)
        showIsland({
          kind: 'toast',
          title: t('redesign.home.mixEditSaved', 'Изменения сохранены'),
          durationMs: 2400,
        })
      } catch {
        showIsland({
          kind: 'error',
          title: t('redesign.home.mixEditSaveFail', 'Не удалось сохранить изменения'),
          durationMs: 3500,
        })
      } finally {
        setSaveBusy(false)
      }
    },
    [normalizedGenre, canEditUi, t],
  )

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

  const availableTracks = useMemo(() => {
    const inMix = new Set((tracks ?? []).map((tr) => tr.id))
    const q = trackSearch.trim().toLowerCase()
    const local = trackPool
      .filter((tr) => !inMix.has(tr.id))
      .filter((tr) => {
        if (!q) return true
        const hay = `${tr.title} ${tr.artist ?? ''}`.toLowerCase()
        return hay.includes(q)
      })
    const merged = [...local]
    for (const remote of searchResults) {
      if (
        !inMix.has(remote.id) &&
        !merged.some((tr) => tr.id === remote.id)
      ) {
        merged.push(remote)
      }
    }
    return merged
  }, [tracks, trackPool, trackSearch, searchResults])

  const applyTitle = useCallback(async () => {
    const nextTitle = titleDraft.trim() || title
    const nextTracks = tracks ?? []
    setTitle(nextTitle)
    await persistOverride(nextTitle, nextTracks)
  }, [titleDraft, title, tracks, persistOverride])

  const moveTrack = useCallback(
    async (index: number, dir: -1 | 1) => {
      if (!tracks) return
      const next = [...tracks]
      const to = index + dir
      if (to < 0 || to >= next.length) return
      const tmp = next[index]
      next[index] = next[to]
      next[to] = tmp
      setTracks(next)
      await persistOverride(title, next)
    },
    [tracks, title, persistOverride],
  )

  const removeTrack = useCallback(
    async (trackId: number) => {
      const next = (tracks ?? []).filter((tr) => tr.id !== trackId)
      setTracks(next)
      await persistOverride(title, next)
    },
    [tracks, title, persistOverride],
  )

  const addTrack = useCallback(async () => {
    if (!addTrackId) return
    const candidate = availableTracks.find((tr) => tr.id === addTrackId)
    if (!candidate) return
    const next = [...(tracks ?? []), candidate]
    setTracks(next)
    setAddTrackId(null)
    await persistOverride(title, next)
  }, [addTrackId, availableTracks, tracks, title, persistOverride])

  return (
    <section className="view active">
      <div className="view-header">
        <MotionPress
          type="button"
          variant="icon"
          haptic="light"
          className="icon-btn"
          ariaLabel={t('redesign.home.back', 'Назад')}
          onClick={() => navigate(-1)}
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </MotionPress>
        <div className="rh-mix-headline">
          <h2>{title}</h2>
          {tracks !== null && (
            <span className="hint">
              {t('redesign.home.mixHeaderTracks', {
                count: tracks.length,
                defaultValue: `${tracks.length} треков`,
              })}
            </span>
          )}
        </div>
        {tracks && tracks.length > 0 && (
          <div className="rh-mix-header-actions">
            {canEditUi && (
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t('redesign.home.mixEditAria', 'Редактировать микс')}
                onClick={() => {
                  void openEditMode()
                }}
              >
                <Icon name="edit" size={18} />
              </MotionPress>
            )}
            <MotionPress
              type="button"
              variant="icon"
              haptic="light"
              className="icon-btn"
              ariaLabel={t('redesign.home.mixShareAria', 'Поделиться')}
              onClick={() => {
                void openShareModal()
              }}
            >
              <Icon name="share" size={18} />
            </MotionPress>
            <MotionPress
              type="button"
              variant="icon"
              haptic="medium"
              className="icon-btn"
              ariaLabel={t('redesign.home.mixPlayAllAria', 'Слушать всё')}
              onClick={handlePlayAll}
            >
              <MorphIcon name="play" size={20} filled />
            </MotionPress>
          </div>
        )}
      </div>

      {tracks && tracks.length > 0 && mixCoverUrl(tracks[0].cover_key) && (
        <AmbientStage
          coverUrl={mixCoverUrl(tracks[0].cover_key)}
          className="rh-mix-hero"
        >
          <div className="rh-mix-hero__inner">
            <div>
              <h1 className="rh-mix-hero__title">{title}</h1>
              <p className="rh-mix-hero__hint">
                {t('redesign.home.mixHeaderTracks', {
                  count: tracks.length,
                  defaultValue: `${tracks.length} треков`,
                })}
              </p>
              <div className="rh-mix-actions">
                <MotionPress
                  variant="primary"
                  haptic="medium"
                  onClick={() => {
                    void handlePlayAll()
                  }}
                >
                  {t('redesign.home.mixPlayAll')}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  haptic="light"
                  onClick={() => {
                    void handleShufflePlay()
                  }}
                >
                  {t('redesign.home.mixShuffle')}
                </MotionPress>
              </div>
            </div>
            <div className="rh-mix-hero__cover">
              <KenBurnsCover
                src={mixCoverUrl(tracks[0].cover_key)!}
                alt=""
              />
            </div>
          </div>
        </AmbientStage>
      )}

      <m.div
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
      >
        <TrackList
          tracks={tracks}
          emptyMessage={t(
            'redesign.home.mixEmpty',
            'В этом миксе пока нет треков',
          )}
        />
      </m.div>

      {editOpen && (
        <div
          className="share-modal-overlay fade-in"
          onClick={(e) => {
            if (e.target === e.currentTarget) setEditOpen(false)
          }}
        >
          <div className="share-modal scale-in gm-edit-modal">
            <div className="share-modal-header">
              <div className="share-modal-title-wrap">
                <h3 className="share-modal-title">
                  {t('redesign.home.mixEditTitle', 'Редактирование микса')}
                </h3>
                <p className="share-modal-subtitle">
                  {t('redesign.home.mixEditServerHint', 'Серверное сохранение')}
                </p>
              </div>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t('redesign.library.shareClose', 'Закрыть')}
                onClick={() => setEditOpen(false)}
              >
                <Icon name="x" size={18} />
              </MotionPress>
            </div>
            <div className="form-group gm-edit-section">
              <label className="form-label">
                {t('redesign.home.mixEditNameLabel', 'Название')}
              </label>
              <input
                className="form-input gm-edit-input"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
              />
              <MotionPress
                type="button"
                variant="primary"
                haptic="medium"
                className="btn-primary gm-edit-btn"
                onClick={() => {
                  void applyTitle()
                }}
                disabled={saveBusy}
              >
                {saveBusy
                  ? t('redesign.home.mixEditApplying', 'Сохранение...')
                  : t('redesign.home.mixEditApply', 'Применить')}
              </MotionPress>
            </div>
            <div className="gm-edit-add-row">
              <input
                className="form-input gm-edit-input"
                placeholder={t(
                  'redesign.home.mixEditSearchPlaceholder',
                  'Поиск треков: название или артист...',
                )}
                value={trackSearch}
                onChange={(e) => setTrackSearch(e.target.value)}
              />
              <select
                className="form-input gm-edit-input"
                value={addTrackId ?? ''}
                onChange={(e) => setAddTrackId(Number(e.target.value) || null)}
              >
                <option value="">
                  {t('redesign.home.mixEditAddPlaceholder', 'Добавить трек...')}
                </option>
                {availableTracks.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.title} {tr.artist ? `- ${tr.artist}` : ''}
                  </option>
                ))}
              </select>
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="btn-secondary gm-edit-btn"
                onClick={() => {
                  void addTrack()
                }}
                disabled={saveBusy}
              >
                {t('redesign.home.mixEditAdd', 'Добавить')}
              </MotionPress>
            </div>
            {searchLoading && (
              <p className="hint gm-edit-search-hint">
                {t('redesign.home.mixEditSearching', 'Идёт поиск…')}
              </p>
            )}
            <div className="gm-edit-list">
              {(tracks ?? []).map((tr, idx) => (
                <div key={tr.id} className="gm-edit-item">
                  <div className="gm-edit-item-main">
                    <span className="gm-edit-item-title">{tr.title}</span>
                    <span className="gm-edit-item-artist">{tr.artist || '—'}</span>
                  </div>
                  <div className="gm-edit-item-actions">
                    <MotionPress
                      type="button"
                      variant="icon"
                      haptic="light"
                      className="icon-btn gm-edit-icon-btn"
                      ariaLabel={t('redesign.home.mixEditMoveUp', 'Выше')}
                      onClick={() => {
                        void moveTrack(idx, -1)
                      }}
                      disabled={saveBusy}
                    >
                      <Icon name="chevron-up" size={14} />
                    </MotionPress>
                    <MotionPress
                      type="button"
                      variant="icon"
                      haptic="light"
                      className="icon-btn gm-edit-icon-btn"
                      ariaLabel={t('redesign.home.mixEditMoveDown', 'Ниже')}
                      onClick={() => {
                        void moveTrack(idx, 1)
                      }}
                      disabled={saveBusy}
                    >
                      <Icon name="chevron-down" size={14} />
                    </MotionPress>
                    <MotionPress
                      type="button"
                      variant="icon"
                      haptic="light"
                      className="icon-btn gm-edit-icon-btn"
                      ariaLabel={t('redesign.home.mixEditRemove', 'Убрать')}
                      onClick={() => {
                        void removeTrack(tr.id)
                      }}
                      disabled={saveBusy}
                    >
                      <Icon name="x" size={14} />
                    </MotionPress>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

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
                  {t('redesign.library.shareTitleMix', 'Поделиться миксом')}
                </h3>
                <p className="share-modal-subtitle">{title}</p>
              </div>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t('redesign.library.shareCopy', 'Скопировать ссылку')}
                onClick={() => {
                  void handleCopyLink()
                }}
              >
                <Icon name="copy" size={16} />
              </MotionPress>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t('redesign.library.shareClose', 'Закрыть')}
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
                      disabled={shareSendingConvId !== null}
                      onClick={() => {
                        void handleShareToChat(convId)
                      }}
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
                        {sending
                          ? t('redesign.library.shareSending', 'Отправка...')
                          : t('redesign.library.shareSend', 'Отправить')}
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
