import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { api } from '@/lib/api'
import { getInternalUserId, tg } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import type { TrackCardResponse } from '@/types/api'
import { LyricsPanel } from './LyricsPanel'

interface Props {
  onOpenAuthor: (authorId: number) => void
}

const GENERATE_COOLDOWN_MS = 20_000

function coverUrl(key: string, v: number): string {
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}&v=${v}`
}

export function TrackCardSheet({
  onOpenAuthor,
}: Props) {
  const { track, isCardOpen, closeCard } = usePlayer()
  const [card, setCard] =
    useState<TrackCardResponse | null>(null)
  const [showLyrics, setShowLyrics] = useState(false)
  const [authorAvatarUrl, setAuthorAvatarUrl] =
    useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [coverKey, setCoverKey] = useState<
    string | null
  >(null)
  const [coverVer, setCoverVer] = useState(0)
  const [coverBusy, setCoverBusy] = useState(false)
  const [genCooldown, setGenCooldown] = useState(0)

  const sheetRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isCardOpen || !track) {
      setCard(null)
      setShowLyrics(false)
      setAuthorAvatarUrl(null)
      setCoverKey(null)
      setCoverBusy(false)
      return
    }
    setCoverKey(track.cover_key)
    setCoverVer((v) => v + 1)
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
  }, [isCardOpen, track?.id])

  useEffect(() => {
    if (genCooldown <= 0) return
    const t = setInterval(
      () => setGenCooldown((v) => Math.max(0, v - 1)),
      1000,
    )
    return () => clearInterval(t)
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

  const handleUploadCover = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFileSelected = useCallback(
    async (
      e: React.ChangeEvent<HTMLInputElement>,
    ) => {
      const file = e.target.files?.[0]
      if (!file || !track) return
      setCoverBusy(true)
      try {
        const fd = new FormData()
        fd.append('cover', file)
        const updated = await api.uploadTrackCover(
          track.id,
          fd,
        )
        if (updated.cover_key) {
          setCoverKey(updated.cover_key)
          setCoverVer((v) => v + 1)
        }
      } catch {
        tg.showAlert(
          'Не удалось загрузить обложку',
        )
      } finally {
        setCoverBusy(false)
        e.target.value = ''
      }
    },
    [track],
  )

  const handleGenerateCover = useCallback(async () => {
    if (!track || genCooldown > 0) return
    setCoverBusy(true)
    setGenCooldown(
      Math.ceil(GENERATE_COOLDOWN_MS / 1000),
    )
    try {
      await api.regenerateTrackCover(track.id)
      for (let i = 0; i < 10; i++) {
        await new Promise((r) =>
          setTimeout(r, 1500),
        )
        try {
          const updated = await api.getTrack(
            track.id,
          )
          if (
            updated.cover_key &&
            updated.cover_key !== coverKey
          ) {
            setCoverKey(updated.cover_key)
            setCoverVer((v) => v + 1)
            break
          }
        } catch {}
      }
    } catch {
      tg.showAlert(
        'Не удалось сгенерировать обложку',
      )
    } finally {
      setCoverBusy(false)
    }
  }, [track, genCooldown, coverKey])

  if (!isCardOpen || !track) return null

  const coverSrc = coverKey
    ? coverUrl(coverKey, coverVer)
    : null

  const internalId = getInternalUserId()
  const isOwner =
    internalId !== null &&
    track.uploaded_by_id === internalId

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

        <div
          className="tcs-cover-wrap"
          style={{ position: 'relative' }}
        >
          {coverBusy && (
            <div className="tcs-cover-loading">
              <div className="loader" />
            </div>
          )}
          {coverSrc ? (
            <img
              className="tcs-cover"
              src={coverSrc}
              alt=""
            />
          ) : (
            <div className="tcs-cover-placeholder">
              🎵
            </div>
          )}
        </div>

        <div className="tcs-info">
          <h2 className="tcs-title">
            {track.title}
          </h2>
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
            onClick={() =>
              setShowLyrics((v) => !v)
            }
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
                disabled={coverBusy}
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
                  coverBusy || genCooldown > 0
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
