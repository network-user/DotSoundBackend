import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { useToast } from '@/components/ui/Toast'
import { api, getApiErrorMessage } from '@/lib/api'
import { VARIANTS_FADE_UP, m } from '@/lib/motion'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import type {
  ChatListItem,
  UserChoicePlaylistResponse,
} from '@/types/api'

function mixCoverUrl(key: string | null): string | null {
  if (!key) return null
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

export function UserChoiceView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const { playTrack, toggleShuffle } = usePlayerActions()
  const { shuffleOn } = usePlayerMeta()
  const [data, setData] = useState<UserChoicePlaylistResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [shareOpen, setShareOpen] = useState(false)
  const [shareChats, setShareChats] = useState<ChatListItem[]>([])
  const [shareLoading, setShareLoading] = useState(false)
  const [shareSendingConvId, setShareSendingConvId] = useState<number | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)

  const shareUrl = `${window.location.origin}${import.meta.env.BASE_URL}user-choice`

  const load = useCallback(() => {
    setLoading(true)
    api
      .getUserChoicePlaylist(100)
      .then(setData)
      .catch(() =>
        setData({
          tracks: [],
          generated_at: '',
          score_version: '',
        }),
      )
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const tracks = loading ? null : (data?.tracks ?? [])

  usePrefetchTracks(tracks ?? null, 'user_choice')

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

  const playList = tracks ?? []
  const heroArt = playList[0]
  const heroUrl = heroArt ? mixCoverUrl(heroArt.cover_key) : null

  const handlePlayAll = useCallback(async () => {
    if (!playList.length) return
    try {
      await playTrack(playList[0])
    } catch (e) {
      toast.error(getApiErrorMessage(e, 'Playback error'))
    }
  }, [playList, playTrack, toast])

  const handleShufflePlay = useCallback(async () => {
    if (!playList.length) return
    try {
      if (!shuffleOn) toggleShuffle()
      const pick =
        playList[Math.floor(Math.random() * playList.length)]
      await playTrack(pick)
    } catch (e) {
      toast.error(getApiErrorMessage(e, 'Playback error'))
    }
  }, [playList, playTrack, shuffleOn, toggleShuffle, toast])

  return (
    <section className="view active">
      <div className="view-header">
        <button className="icon-btn" type="button" onClick={() => navigate(-1)}>
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div style={{ flex: 1 }}>
          <h2>{t('userChoice.title')}</h2>
          <span className="hint">{t('userChoice.hint')}</span>
        </div>
        <button
          className="icon-btn"
          type="button"
          onClick={() => {
            void openShareModal()
          }}
          aria-label="Поделиться"
        >
          <Icon name="share" size={18} />
        </button>
      </div>

      {!loading && heroUrl && (
        <AmbientStage coverUrl={heroUrl} className="rh-mix-hero">
          <div className="rh-mix-hero__inner">
            <div>
              <h1 className="rh-mix-hero__title">{t('userChoice.title')}</h1>
              <p className="rh-mix-hero__hint">{t('userChoice.hint')}</p>
              <div className="rh-mix-actions">
                <MotionPress
                  variant="primary"
                  onClick={() => {
                    void handlePlayAll()
                  }}
                >
                  {t('redesign.home.mixPlayAll')}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  onClick={() => {
                    void handleShufflePlay()
                  }}
                >
                  {t('redesign.home.mixShuffle')}
                </MotionPress>
              </div>
            </div>
            <div className="rh-mix-hero__cover">
              <KenBurnsCover src={heroUrl} alt="" />
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
          emptyMessage={t('userChoice.empty')}
        />
      </m.div>

      {shareOpen && (
        <div className="share-modal-overlay fade-in" onClick={(e) => {
          if (e.target === e.currentTarget) setShareOpen(false)
        }}>
          <div className="share-modal scale-in">
            <div className="share-modal-header">
              <div className="share-modal-title-wrap">
                <h3 className="share-modal-title">Поделиться плейлистом</h3>
                <p className="share-modal-subtitle">{t('userChoice.title')}</p>
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
