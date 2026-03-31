import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import { tg } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import type { TrackCardResponse } from '@/types/api'
import { LyricsPanel } from './LyricsPanel'

interface Props {
  onOpenAuthor: (authorId: number) => void
}

export function TrackCardSheet({ onOpenAuthor }: Props) {
  const { track, isCardOpen, closeCard } = usePlayer()
  const [card, setCard] = useState<TrackCardResponse | null>(null)
  const [showLyrics, setShowLyrics] = useState(false)
  const [authorAvatarUrl, setAuthorAvatarUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const sheetRef = useRef<HTMLDivElement>(null)

  // Fetch card data when sheet opens
  useEffect(() => {
    if (!isCardOpen || !track) {
      setCard(null)
      setShowLyrics(false)
      setAuthorAvatarUrl(null)
      return
    }
    setLoading(true)
    api.getTrackCard(track.id)
      .then((c) => {
        setCard(c)
        if (c.author?.id) {
          api.getAvatarUrl(c.author.id)
            .then((r) => setAuthorAvatarUrl(r.avatar_url))
            .catch(() => {})
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [isCardOpen, track])

  // Close on backdrop click
  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) closeCard()
  }

  const handleShare = async () => {
    if (!track) return
    try {
      const { telegram_share_url } = await api.getShareLinks(track.id)
      tg.openTelegramLink(telegram_share_url)
    } catch {
      tg.showAlert('Не удалось получить ссылку')
    }
  }

  const handleAuthor = () => {
    if (card?.author?.id) {
      closeCard()
      onOpenAuthor(card.author.id)
    }
  }

  if (!isCardOpen || !track) return null

  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null

  const isOwner = userId !== null && track.uploaded_by_id === userId

  return (
    <div className="tcs-backdrop" onClick={handleBackdrop}>
      <div className="tcs-sheet" ref={sheetRef}>
        {/* Handle bar */}
        <div className="tcs-handle" />

        {/* Close button */}
        <button className="tcs-close icon-btn" onClick={closeCard}>✕</button>

        {/* Cover */}
        <div className="tcs-cover-wrap">
          {coverSrc ? (
            <img
              className="tcs-cover"
              src={coverSrc}
              alt=""
              onError={(e) => {
                const el = e.currentTarget
                el.style.display = 'none'
                el.parentElement!.querySelector('.tcs-cover-placeholder')?.removeAttribute('style')
              }}
            />
          ) : null}
          <div
            className="tcs-cover-placeholder"
            style={coverSrc ? { display: 'none' } : undefined}
          >
            🎵
          </div>
        </div>

        {/* Track info */}
        <div className="tcs-info">
          <h2 className="tcs-title">{track.title}</h2>
          <p className="tcs-artist">{track.artist ?? '—'}</p>

          {/* Author row */}
          {card?.author && (
            <div className="tcs-author-row" onClick={handleAuthor}>
              <div className="tcs-author-avatar">
                {authorAvatarUrl ? (
                  <img src={authorAvatarUrl} alt="" onError={(e) => { e.currentTarget.style.display = 'none' }} />
                ) : (
                  '👤'
                )}
              </div>
              <span className="tcs-author-name">
                {card.author.display_name || card.author.username || 'Автор'}
              </span>
              <span className="tcs-author-chevron">›</span>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="tcs-actions">
          <button
            className={`tcs-action-btn${showLyrics ? ' active' : ''}`}
            onClick={() => setShowLyrics((v) => !v)}
            disabled={!card?.has_lyrics && !isOwner}
          >
            <span className="tcs-action-icon">🎵</span>
            <span className="tcs-action-label">
              {isOwner && !card?.has_lyrics ? 'Добавить текст' : 'Текст'}
            </span>
          </button>

          <button className="tcs-action-btn" onClick={handleShare}>
            <span className="tcs-action-icon">🔗</span>
            <span className="tcs-action-label">Поделиться</span>
          </button>

          <button
            className="tcs-action-btn"
            onClick={handleAuthor}
            disabled={!card?.author}
          >
            <span className="tcs-action-icon">👤</span>
            <span className="tcs-action-label">К автору</span>
          </button>

          {card?.album && (
            <button className="tcs-action-btn">
              <span className="tcs-action-icon">💿</span>
              <span className="tcs-action-label">{card.album.title}</span>
            </button>
          )}
        </div>

        {/* Lyrics / editor panel */}
        {showLyrics && track && (
          <LyricsPanel
            trackId={track.id}
            isOwner={isOwner}
            hasLyrics={card?.has_lyrics ?? false}
          />
        )}

        {loading && !card && (
          <div className="tcs-loader">
            <div className="loader" />
          </div>
        )}
      </div>
    </div>
  )
}
