import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import { renderRoundedQrDataUrl } from '@/lib/roundedQr'
import {
  copyToClipboard,
  getShareCapabilities,
  shareNatively,
} from '@/lib/platform'
import { showIsland } from '@/lib/island'
import { formatPlays } from '@/lib/utils'
import type {
  ArtistShareCardResponse,
  ShareCardResponse,
} from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
  userId?: number
  artistId?: number
  initialShowQr?: boolean
}

type LoadedUser = { kind: 'user'; data: ShareCardResponse }
type LoadedArtist = { kind: 'artist'; data: ArtistShareCardResponse }
type Loaded = LoadedUser | LoadedArtist

export function ProfileShareModal({
  open,
  onClose,
  userId,
  artistId,
  initialShowQr = false,
}: Props) {
  const { t } = useTranslation()
  const [card, setCard] = useState<Loaded | null>(null)
  const [loading, setLoading] = useState(false)
  const [showQr, setShowQr] = useState(false)
  const [qrDataUrl, setQrDataUrl] = useState('')
  const previewRef = useRef<HTMLDivElement | null>(null)

  const caps = useMemo(() => getShareCapabilities(), [])

  const isUserMode = Boolean(userId && !artistId)
  const isArtistMode = Boolean(artistId && !userId)

  useEffect(() => {
    if (open) {
      setShowQr(Boolean(initialShowQr))
    }
  }, [open, initialShowQr])

  useEffect(() => {
    if (!open) return
    if (!isUserMode && !isArtistMode) return
    setLoading(true)
    let cancelled = false
    const p = isUserMode
      ? api.getProfileShareCard(userId as number)
      : api.getArtistShareCard(artistId as number)
    p.then((res) => {
      if (cancelled) return
      if (isUserMode) {
        setCard({ kind: 'user', data: res as ShareCardResponse })
      } else {
        setCard({
          kind: 'artist',
          data: res as ArtistShareCardResponse,
        })
      }
    })
      .catch(() => {
        if (!cancelled) setCard(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, userId, artistId, isUserMode, isArtistMode])

  const shareUrl = useMemo(() => {
    if (!card) return ''
    if (card.kind === 'user') {
      return card.data.deep_link || card.data.profile_url || ''
    }
    return card.data.deep_link || card.data.profile_url || ''
  }, [card])

  useEffect(() => {
    if (!shareUrl || !showQr) {
      setQrDataUrl('')
      return
    }
    let cancelled = false
    void renderRoundedQrDataUrl(shareUrl, 272).then((url) => {
      if (!cancelled && url) setQrDataUrl(url)
    })
    return () => {
      cancelled = true
    }
  }, [shareUrl, showQr])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () =>
      document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const modalTitle = isArtistMode
    ? t('artist.shareTitle', 'Поделиться артистом')
    : t('profile.share.title', 'Поделиться профилем')

  const handleCopy = async () => {
    if (!shareUrl) return
    const ok = await copyToClipboard(shareUrl)
    showIsland({
      kind: ok ? 'toast' : 'error',
      title: ok
        ? t('profile.share.copied', 'Ссылка скопирована')
        : t('profile.share.copyFail', 'Не удалось скопировать'),
      iconName: ok ? 'check' : 'alert-triangle',
      durationMs: 2200,
    })
  }

  const handleShare = async () => {
    if (!shareUrl || !card) return
    const title =
      card.kind === 'user'
        ? card.data.display_name
        : card.data.display_name
    const ok = await shareNatively({
      url: shareUrl,
      title,
      text: t('profile.share.shareText', {
        defaultValue: '{{name}} в DotSound',
        name: title,
      }),
    })
    if (!ok) {
      await handleCopy()
    }
  }

  const node = (
    <div
      className="rp-share-modal"
      role="dialog"
      aria-modal="true"
      aria-label={modalTitle}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="rp-share-modal__panel">
        <div className="rp-share-modal__head">
          <h2 className="rp-share-modal__title">{modalTitle}</h2>
          <button
            type="button"
            className="rp-share-modal__close"
            aria-label={t('profile.share.close', 'Закрыть')}
            onClick={onClose}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        {loading && (
          <div className="rp-share-loading">
            {t('profile.share.loading', 'Загрузка…')}
          </div>
        )}

        {!loading && card && (
          <>
            <div
              ref={previewRef}
              className="rp-share-preview"
            >
              <div className="rp-share-preview__avatar">
                {card.kind === 'user' && card.data.avatar_url ? (
                  <img
                    src={card.data.avatar_url}
                    alt=""
                    crossOrigin="anonymous"
                  />
                ) : card.kind === 'artist' && card.data.image_url ? (
                  <img
                    src={card.data.image_url}
                    alt=""
                    crossOrigin="anonymous"
                  />
                ) : (
                  <span>
                    {card.data.display_name
                      .charAt(0)
                      .toUpperCase()}
                  </span>
                )}
              </div>
              <div className="rp-share-preview__name">
                {card.data.display_name}
              </div>
              {card.kind === 'user' && card.data.username && (
                <div className="rp-share-preview__username">
                  @{card.data.username}
                </div>
              )}
              <div className="rp-share-preview__stats">
                <div>
                  <div className="rp-share-preview__stat-value">
                    {card.kind === 'user'
                      ? card.data.total_tracks
                      : card.data.total_tracks}
                  </div>
                  <div className="rp-share-preview__stat-label">
                    {t('profile.share.tracks', 'Треков')}
                  </div>
                </div>
                <div>
                  <div className="rp-share-preview__stat-value">
                    {card.kind === 'user'
                      ? formatPlays(card.data.total_plays)
                      : formatPlays(card.data.monthly_listeners)}
                  </div>
                  <div className="rp-share-preview__stat-label">
                    {card.kind === 'user'
                      ? t('profile.share.plays', 'Прослушив.')
                      : t(
                          'artist.shareMonthlyListeners',
                          'Слушателей / мес.',
                        )}
                  </div>
                </div>
                <div>
                  <div className="rp-share-preview__stat-value">
                    {card.kind === 'user'
                      ? card.data.followers_count
                      : card.data.followers_count}
                  </div>
                  <div className="rp-share-preview__stat-label">
                    {t('profile.share.followers', 'Подписч.')}
                  </div>
                </div>
              </div>
            </div>

            {showQr && (
              <div className="rp-share-qr">
                {qrDataUrl ? (
                  <div className="rp-share-qr__shell">
                    <img
                      className="rp-share-qr__img"
                      src={qrDataUrl}
                      alt=""
                      width={272}
                      height={272}
                    />
                  </div>
                ) : (
                  <div className="rp-share-loading rp-share-loading--compact">
                    {t('profile.share.loading', 'Загрузка…')}
                  </div>
                )}
              </div>
            )}

            <div className="rp-share-inline">
              <MotionPress
                type="button"
                variant="primary"
                haptic="medium"
                className="rp-share-inline__btn"
                data-variant="primary"
                onClick={() => void handleShare()}
                disabled={!shareUrl}
              >
                <Icon
                  name={caps.telegram ? 'send' : 'share'}
                  size={16}
                />
                <span>
                  {caps.telegram
                    ? t('profile.share.shareTelegram', 'В Telegram')
                    : t('profile.share.shareNative', 'Поделиться')}
                </span>
              </MotionPress>
              <MotionPress
                type="button"
                variant={showQr ? 'primary' : 'ghost'}
                haptic="light"
                className="rp-share-inline__btn"
                aria-pressed={showQr}
                onClick={() => setShowQr((v) => !v)}
                disabled={!shareUrl}
              >
                <Icon name="share-arrow" size={16} />
                <span>
                  {t('profile.share.tabQr', 'QR')}
                </span>
              </MotionPress>
            </div>
          </>
        )}
      </div>
    </div>
  )

  if (typeof document === 'undefined') return null
  return createPortal(node, document.body)
}
