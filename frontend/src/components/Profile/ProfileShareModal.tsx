import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import QRCode from 'qrcode'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import {
  copyToClipboard,
  getShareCapabilities,
  shareNatively,
} from '@/lib/platform'
import { showIsland } from '@/lib/island'
import { formatPlays } from '@/lib/utils'
import type { ShareCardResponse } from '@/types/api'

type Tab = 'link' | 'qr' | 'card'

interface Props {
  open: boolean
  userId: number
  onClose: () => void
  initialTab?: Tab
}

export function ProfileShareModal({
  open,
  userId,
  onClose,
  initialTab = 'link',
}: Props) {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>(initialTab)

  useEffect(() => {
    if (open) setTab(initialTab)
  }, [open, initialTab])
  const [card, setCard] = useState<ShareCardResponse | null>(
    null,
  )
  const [loading, setLoading] = useState(false)
  const [qrSvg, setQrSvg] = useState<string>('')
  const previewRef = useRef<HTMLDivElement | null>(null)

  const caps = useMemo(() => getShareCapabilities(), [])

  useEffect(() => {
    if (!open) return
    setLoading(true)
    let cancelled = false
    api
      .getProfileShareCard(userId)
      .then((res) => {
        if (!cancelled) setCard(res)
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
  }, [open, userId])

  const shareUrl =
    card?.deep_link || card?.profile_url || ''

  useEffect(() => {
    if (!shareUrl) {
      setQrSvg('')
      return
    }
    QRCode.toString(shareUrl, {
      type: 'svg',
      margin: 1,
      errorCorrectionLevel: 'M',
      color: { dark: '#0a0a0aff', light: '#00000000' },
    })
      .then((svg) => setQrSvg(svg))
      .catch(() => setQrSvg(''))
  }, [shareUrl])

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
    const ok = await shareNatively({
      url: shareUrl,
      title: card.display_name,
      text: t('profile.share.shareText', {
        defaultValue: '{{name}} в DotSound',
        name: card.display_name,
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
      aria-label={t('profile.share.title', 'Поделиться профилем')}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="rp-share-modal__panel">
        <div className="rp-share-modal__head">
          <h2 className="rp-share-modal__title">
            {t('profile.share.title', 'Поделиться профилем')}
          </h2>
          <button
            type="button"
            className="rp-share-modal__close"
            aria-label={t('profile.share.close', 'Закрыть')}
            onClick={onClose}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div role="tablist" className="rp-share-tabs">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'link'}
            className="rp-share-tab"
            onClick={() => setTab('link')}
          >
            {t('profile.share.tabLink', 'Ссылка')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'qr'}
            className="rp-share-tab"
            onClick={() => setTab('qr')}
          >
            {t('profile.share.tabQr', 'QR')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'card'}
            className="rp-share-tab"
            onClick={() => setTab('card')}
          >
            {t('profile.share.tabCard', 'Карточка')}
          </button>
        </div>

        {loading && (
          <div
            style={{
              padding: 24,
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: 13,
            }}
          >
            {t('profile.share.loading', 'Загрузка…')}
          </div>
        )}

        {!loading && tab === 'link' && card && (
          <div className="rp-share-link">
            <span className="rp-share-link__url">
              {shareUrl}
            </span>
            <button
              type="button"
              className="rp-share-link__copy"
              onClick={handleCopy}
            >
              {t('profile.share.copy', 'Копировать')}
            </button>
          </div>
        )}

        {!loading && tab === 'qr' && (
          <div className="rp-share-qr">
            {qrSvg ? (
              <div
                className="rp-share-qr__frame"
                aria-label="QR"
                dangerouslySetInnerHTML={{ __html: qrSvg }}
              />
            ) : (
              <span className="rp-share-qr__fail">
                {t('profile.share.qrFail', 'QR недоступен')}
              </span>
            )}
          </div>
        )}

        {!loading && tab === 'card' && card && (
          <div
            ref={previewRef}
            className="rp-share-preview"
          >
            <div className="rp-share-preview__avatar">
              {card.avatar_url ? (
                <img
                  src={card.avatar_url}
                  alt=""
                  crossOrigin="anonymous"
                />
              ) : (
                <span>
                  {card.display_name.charAt(0).toUpperCase()}
                </span>
              )}
            </div>
            <div className="rp-share-preview__name">
              {card.display_name}
            </div>
            {card.username && (
              <div className="rp-share-preview__username">
                @{card.username}
              </div>
            )}
            <div className="rp-share-preview__stats">
              <div>
                <div className="rp-share-preview__stat-value">
                  {card.total_tracks}
                </div>
                <div className="rp-share-preview__stat-label">
                  {t('profile.share.tracks', 'Треков')}
                </div>
              </div>
              <div>
                <div className="rp-share-preview__stat-value">
                  {formatPlays(card.total_plays)}
                </div>
                <div className="rp-share-preview__stat-label">
                  {t('profile.share.plays', 'Прослушив.')}
                </div>
              </div>
              <div>
                <div className="rp-share-preview__stat-value">
                  {card.followers_count}
                </div>
                <div className="rp-share-preview__stat-label">
                  {t('profile.share.followers', 'Подписч.')}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="rp-share-actions">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="rp-share-actions__btn"
            onClick={handleCopy}
            disabled={!shareUrl}
          >
            <Icon name="copy" size={14} />
            <span>
              {t('profile.share.copy', 'Копировать')}
            </span>
          </MotionPress>
          <MotionPress
            type="button"
            variant="primary"
            haptic="medium"
            className="rp-share-actions__btn"
            data-variant="primary"
            onClick={handleShare}
            disabled={!shareUrl}
          >
            <Icon
              name={caps.telegram ? 'send' : 'share'}
              size={14}
            />
            <span>
              {caps.telegram
                ? t('profile.share.shareTelegram', 'В Telegram')
                : t('profile.share.shareNative', 'Поделиться')}
            </span>
          </MotionPress>
        </div>
      </div>
    </div>
  )

  if (typeof document === 'undefined') return null
  return createPortal(node, document.body)
}
