import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import { tg } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import type { TrackCardResponse } from '@/types/api'
import { LyricsPanel } from './LyricsPanel'

interface Props {
  onOpenAuthor: (authorId: number) => void
}

const GENERATE_COOLDOWN_MS = 20_000

export function TrackCardSheet({ onOpenAuthor }: Props) {
  const { track, isCardOpen, closeCard, playTrack } =
    usePlayer()
  const [card, setCard] =
    useState<TrackCardResponse | null>(null)
  const [showLyrics, setShowLyrics] = useState(false)
  const [authorAvatarUrl, setAuthorAvatarUrl] =
    useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [coverVersion, setCoverVersion] = useState(0)
  const [genCooldown, setGenCooldown] = useState(0)
  const [coverUploading, setCoverUploading] =
    useState(false)
  const sheetRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isCardOpen || !track) {
      setCard(null)
      setShowLyrics(false)
      setAuthorAvatarUrl(null)
      return
    }
    setLoading(true)
    api
      .getTrackCard(track.id)
      .then((c) => {
        setCard(c)
        if (c.author?.id) {
          api
            .getAvatarUrl(c.author.id)
            .then((r) =>
              setAuthorAvatarUrl(r.avatar_url),
            )
            .catch(() => {})
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [isCardOpen, track])

  useEffect(() => {
    if (genCooldown <= 0) return
    const timer = setInterval(() => {
      setGenCooldown((v) => Math.max(0, v - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [genCooldown])

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) closeCard()
  }

  const handleShare = async () => {
    if (!track) return
    try {
      const { telegram_share_url } =
        await api.getShareLinks(track.id)
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

  const handleUploadCover = useCallback(async () => {
    fileInputRef.current?.click()
  }, [])

  const handleFileSelected = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file || !track) return
      setCoverUploading(true)
      try {
        const fd = new FormData()
        fd.append('cover', file)
        const updated =
          await api.uploadTrackCover(track.id, fd)
        if (updated.cover_key) {
          track.cover_key = updated.cover_key
          setCoverVersion((v) => v + 1)
        }
      } catch {
        tg.showAlert('Не удалось загрузить обложку')
      } finally {
        setCoverUploading(false)
        e.target.value = ''
      }
    },
    [track],
  )

  const handleGenerateCover = useCallback(async () => {
    if (!track || genCooldown > 0) return
    setCoverUploading(true)
    try {
      await api.regenerateTrackCover(track.id)
      setGenCooldown(
        Math.ceil(GENERATE_COOLDOWN_MS / 1000),
      )
      setTimeout(async () => {
        try {
          const updated = await api.getTrack(track.id)
          if (updated.cover_key) {
            track.cover_key = updated.cover_key
            setCoverVersion((v) => v + 1)
          }
        } catch {}
      }, 3000)
    } catch {
      tg.showAlert('Не удалось сгенерировать обложку')
    } finally {
      setCoverUploading(false)
    }
  }, [track, genCooldown])

  if (!isCardOpen || !track) return null

  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}&v=${coverVersion}`
    : null

  const isOwner =
    userId !== null &&
    track.uploaded_by_id === userId

  return (
    <div
      className="tcs-backdrop"
      onClick={handleBackdrop}
    >
      <div className="tcs-sheet" ref={sheetRef}>
        <div className="tcs-handle" />
        <button
          className="tcs-close icon-btn"
          onClick={closeCard}
        >
          ✕
        </button>

        <div className="tcs-cover-wrap">
          {coverUploading && (
            <div className="tcs-cover-loading">
              <div className="loader" />
            </div>
          )}
          {coverSrc ? (
            <img
              className="tcs-cover"
              src={coverSrc}
              alt=""
              onError={(e) => {
                const el = e.currentTarget
                el.style.display = 'none'
                el.parentElement!
                  .querySelector(
                    '.tcs-cover-placeholder',
                  )
                  ?.removeAttribute('style')
              }}
            />
          ) : null}
          <div
            className="tcs-cover-placeholder"
            style={
              coverSrc
                ? { display: 'none' }
                : undefined
            }
          >
            🎵
          </div>
        </div>

        <div className="tcs-info">
          <h2 className="tcs-title">{track.title}</h2>
          <p className="tcs-artist">
            {track.artist ?? '—'}
          </p>

          {card?.author && (
            <div
              className="tcs-author-row"
              onClick={handleAuthor}
            >
              <div className="tcs-author-avatar">
                {authorAvatarUrl ? (
                  <img
                    src={authorAvatarUrl}
                    alt=""
                    onError={(e) => {
                      e.currentTarget.style.display =
                        'none'
                    }}
                  />
                ) : (
                  '👤'
                )}
              </div>
              <span className="tcs-author-name">
                {card.author.display_name ||
                  card.author.username ||
                  'Автор'}
              </span>
              <span className="tcs-author-chevron">
                ›
              </span>
            </div>
          )}
        </div>

        <div className="tcs-actions">
          <button
            className={`tcs-action-btn${showLyrics ? ' active' : ''}`}
            onClick={() => setShowLyrics((v) => !v)}
            disabled={
              !card?.has_lyrics && !isOwner
            }
          >
            <span className="tcs-action-icon">
              🎵
            </span>
            <span className="tcs-action-label">
              {isOwner && !card?.has_lyrics
                ? 'Добавить текст'
                : 'Текст'}
            </span>
          </button>

          <button
            className="tcs-action-btn"
            onClick={handleShare}
          >
            <span className="tcs-action-icon">
              🔗
            </span>
            <span className="tcs-action-label">
              Поделиться
            </span>
          </button>

          <button
            className="tcs-action-btn"
            onClick={handleAuthor}
            disabled={!card?.author}
          >
            <span className="tcs-action-icon">
              👤
            </span>
            <span className="tcs-action-label">
              К автору
            </span>
          </button>

          {card?.album && (
            <button className="tcs-action-btn">
              <span className="tcs-action-icon">
                💿
              </span>
              <span className="tcs-action-label">
                {card.album.title}
              </span>
            </button>
          )}

          {isOwner && (
            <>
              <button
                className="tcs-action-btn"
                onClick={handleUploadCover}
                disabled={coverUploading}
              >
                <span className="tcs-action-icon">
                  🖼
                </span>
                <span className="tcs-action-label">
                  Загрузить обложку
                </span>
              </button>

              <button
                className="tcs-action-btn"
                onClick={handleGenerateCover}
                disabled={
                  coverUploading || genCooldown > 0
                }
              >
                <span className="tcs-action-icon">
                  ✨
                </span>
                <span className="tcs-action-label">
                  {genCooldown > 0
                    ? `Подождите ${genCooldown}с`
                    : 'Сгенерировать'}
                </span>
              </button>
            </>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: 'none' }}
          onChange={handleFileSelected}
        />

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
