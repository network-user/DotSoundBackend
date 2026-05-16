import React, { useEffect, useMemo, useRef, useState } from 'react'
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
import { extractCoverPalette, type CoverPalette } from '@/lib/coverPalette'
import { coverProxyUrl as buildCoverProxyUrl } from '@/lib/coverProxy'
import { useFocusTrap } from '@/hooks/useFocusTrap'

function hexToRgba(hex: string, alpha: number): string {
  const v = hex.replace('#', '')
  const r = parseInt(v.slice(0, 2), 16)
  const g = parseInt(v.slice(2, 4), 16)
  const b = parseInt(v.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

export type TrackShareEntityType = 'track' | 'album' | 'playlist'

export interface TrackSharePayload {
  id: number
  type: TrackShareEntityType
  title: string
  subtitle?: string
  coverUrl?: string | null
}

interface Props {
  open: boolean
  onClose: () => void
  payload: TrackSharePayload | null
}

function coverProxyUrl(key: string | null | undefined): string | null {
  if (!key) return null
  return buildCoverProxyUrl(key, { width: 480 })
}

function buildShareUrl(payload: TrackSharePayload, trackUrl: string): string {
  if (payload.type === 'track') return trackUrl
  const base = `${window.location.origin}${import.meta.env.BASE_URL ?? '/'}`
  if (payload.type === 'album')
    return `${base}library?shareType=album&id=${payload.id}`
  return `${base}playlists?shareType=playlist&id=${payload.id}`
}

export function TrackShareModal({ open, onClose, payload }: Props) {
  const { t } = useTranslation()
  const [trackUrl, setTrackUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [showQr, setShowQr] = useState(false)
  const [qrDataUrl, setQrDataUrl] = useState('')
  const [palette, setPalette] = useState<CoverPalette | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)
  useFocusTrap(panelRef, open && payload !== null)

  const caps = useMemo(() => getShareCapabilities(), [])

  const coverSrc = useMemo(() => {
    if (!payload?.coverUrl) return null
    return payload.coverUrl.startsWith('/api/')
      ? payload.coverUrl
      : coverProxyUrl(payload.coverUrl)
  }, [payload?.coverUrl])

  useEffect(() => {
    if (!open || !payload) {
      setTrackUrl(null)
      setShowQr(false)
      setQrDataUrl('')
      setPalette(null)
      return
    }
    if (payload.type !== 'track') {
      setTrackUrl('')
      setLoading(false)
      return
    }
    setLoading(true)
    let cancelled = false
    api
      .getShareLinks(payload.id)
      .then((res) => {
        if (!cancelled) setTrackUrl(res.url)
      })
      .catch(() => {
        if (!cancelled) setTrackUrl(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, payload?.id, payload?.type])

  const shareUrl = useMemo(() => {
    if (!payload) return ''
    if (payload.type === 'track') return trackUrl ?? ''
    return buildShareUrl(payload, '')
  }, [payload, trackUrl])

  useEffect(() => {
    let cancelled = false
    void extractCoverPalette(coverSrc).then((p) => {
      if (!cancelled) setPalette(p)
    })
    return () => { cancelled = true }
  }, [coverSrc])

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
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open || !payload) return null

  const modalTitle =
    payload.type === 'album'
      ? t('share.albumTitle', 'Поделиться альбомом')
      : payload.type === 'playlist'
        ? t('share.playlistTitle', 'Поделиться плейлистом')
        : t('share.trackTitle', 'Поделиться треком')

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
    if (!shareUrl) return
    const ok = await shareNatively({
      url: shareUrl,
      title: payload.title,
      text: payload.subtitle
        ? `${payload.title} — ${payload.subtitle}`
        : payload.title,
    })
    if (!ok) await handleCopy()
  }

  const ready = !loading && (payload.type !== 'track' || trackUrl !== null)

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
      <div className="rp-share-modal__panel" ref={panelRef}>
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

        {ready && (
          <>
            <div
              className="rp-share-preview rp-share-preview--track"
              style={palette ? {
                '--rp-hero-tone-1': hexToRgba(palette.tones[0], 0.34),
                '--rp-hero-tone-2': hexToRgba(palette.tones[1], 0.22),
              } as React.CSSProperties : undefined}
            >
              <div className="rp-share-preview__avatar rp-share-preview__avatar--square">
                {coverSrc ? (
                  <img src={coverSrc} alt="" crossOrigin="anonymous" />
                ) : (
                  <span>
                    <Icon name="music" size={28} />
                  </span>
                )}
              </div>
              <div className="rp-share-preview__name">
                {payload.title}
              </div>
              {payload.subtitle && (
                <div className="rp-share-preview__username">
                  {payload.subtitle}
                </div>
              )}
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
                <Icon name={caps.telegram ? 'send' : 'share'} size={16} />
                <span>
                  {caps.telegram
                    ? t('profile.share.shareTelegram', 'В Telegram')
                    : t('profile.share.shareNative', 'Поделиться')}
                </span>
              </MotionPress>
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="rp-share-inline__btn"
                onClick={() => void handleCopy()}
                disabled={!shareUrl}
              >
                <Icon name="copy" size={16} />
                <span>{t('share.copyLink', 'Скопировать')}</span>
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
                <span>{t('profile.share.tabQr', 'QR')}</span>
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
