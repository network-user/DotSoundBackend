import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type {
  ChatListItem,
  DailyPlaylistResponse,
} from '@/types/api'

export function DailyMixView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState<DailyPlaylistResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const [shareChats, setShareChats] = useState<ChatListItem[]>([])
  const [shareLoading, setShareLoading] = useState(false)
  const [shareSendingConvId, setShareSendingConvId] = useState<number | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)

  const shareUrl = `${window.location.origin}${import.meta.env.BASE_URL}daily-mix`

  const load = useCallback(() => {
    setLoading(true)
    api.getDailyPlaylist()
      .then(setData)
      .catch(() =>
        setData({
          internal_tracks: [],
          external_tracks: [],
          global_top: [],
          generated_at: '',
          expires_at: '',
        }),
      )
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    api.refreshDailyPlaylist()
      .then(() => load())
      .catch(() => load())
      .finally(() => setRefreshing(false))
  }, [load])

  const internalTracks = loading ? null : (data?.internal_tracks ?? [])
  const externalTracks = data?.external_tracks ?? []

  const formatShareChatTitle = useCallback((item: ChatListItem): string => {
    if (item.conversation.type === 'saved') {
      return 'Избранное'
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

  return (
    <section className="view active">
      <div className="view-header">
        <button className="icon-btn" onClick={() => navigate(-1)}>
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div style={{ flex: 1 }}>
          <h2>{t('dailyMix.title')}</h2>
          <span className="hint">{t('dailyMix.hint')}</span>
        </div>
        <button
          className="icon-btn"
          onClick={() => {
            void openShareModal()
          }}
          aria-label="Поделиться"
        >
          <Icon name="share" size={18} />
        </button>
        <button
          className="icon-btn"
          onClick={handleRefresh}
          disabled={refreshing || loading}
          aria-label={t('dailyMix.refreshAria')}
        >
          <Icon
            name="refresh"
            size={20}
            className={refreshing ? 'spin' : undefined}
          />
        </button>
      </div>

      <TrackList
        tracks={internalTracks}
        emptyMessage={t('dailyMix.empty')}
      />

      {!loading && externalTracks.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">{t('dailyMix.discoveries')}</span>
          </div>
          <TrackList tracks={externalTracks} emptyMessage="" />
        </>
      )}

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
                <p className="share-modal-subtitle">{t('dailyMix.title')}</p>
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
                        {sending ? 'Отправка...' : 'Отправить'}
                      </span>
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
