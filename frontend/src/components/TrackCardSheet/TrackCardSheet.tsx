import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { api } from '@/lib/api'
import {
  getInternalUserId,
  tg,
} from '@/lib/telegram'
import { useLikes } from '@/store/LikesContext'
import { usePlayer } from '@/store/PlayerContext'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import type { Track, TrackCardResponse } from '@/types/api'
import { LyricsPanel } from './LyricsPanel'

interface Props {
  onOpenAuthor: (authorId: number) => void
  onOpenArtist?: (name: string) => void
}

const GENERATE_COOLDOWN_MS = 20_000

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

function coverUrl(k: string, v: number) {
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(k)}&v=${v}`
}

export function TrackCardSheet({
  onOpenAuthor,
  onOpenArtist,
}: Props) {
  const {
    track,
    isCardOpen,
    closeCard,
    isPlaying,
    currentTime,
    duration,
    volume,
    setVolume,
    togglePlay,
    seek,
    playNext,
    playPrev,
    openLyrics,
    openComplaint,
    updateTrack,
    playTrack,
  } = usePlayer()
  const {
    isLiked,
    toggleLike,
    isDisliked,
    toggleDislike,
  } = useLikes()

  const [card, setCard] =
    useState<TrackCardResponse | null>(null)
  const [showLyrics, setShowLyrics] =
    useState(false)
  const [editingLyrics, setEditingLyrics] =
    useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [similarTracks, setSimilarTracks] =
    useState<Track[]>([])
  const [authorAvatarUrl, setAuthorAvatarUrl] =
    useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [coverKey, setCoverKey] = useState<
    string | null
  >(null)
  const [coverVer, setCoverVer] = useState(0)
  const [coverBusy, setCoverBusy] = useState(false)
  const [coverFailed, setCoverFailed] =
    useState(false)
  const [genCooldown, setGenCooldown] = useState(0)
  const [videoReady, setVideoReady] =
    useState(false)
  const videoEnabled =
    localStorage.getItem('setting-video-enabled') !== 'false'

  const sheetRef = useRef<HTMLDivElement>(null)
  const coverInputRef =
    useRef<HTMLInputElement>(null)
  const videoInputRef =
    useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isCardOpen || !track) {
      setCard(null)
      setShowLyrics(false)
      setEditingLyrics(false)
      setShowEdit(false)
      setAuthorAvatarUrl(null)
      setCoverKey(null)
      setCoverBusy(false)
      setVideoReady(false)
      return
    }
    setCoverKey(track.cover_key)
    setCoverVer((v) => v + 1)
    setCoverFailed(false)
    setShowEdit(false)
    setVideoReady(false)
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

    setSimilarTracks([])
    api.getSimilarTracks(track.id)
      .then((r) => setSimilarTracks(r.tracks))
      .catch(() => {})
  }, [isCardOpen, track?.id])

  useEffect(() => {
    if (genCooldown <= 0) return
    const t = setInterval(
      () =>
        setGenCooldown((v) => Math.max(0, v - 1)),
      1000,
    )
    return () => clearInterval(t)
  }, [genCooldown])

  const handleBackdrop = (
    e: React.MouseEvent,
  ) => {
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

  const handleCoverUpload = useCallback(
    () => coverInputRef.current?.click(),
    [],
  )

  const handleCoverSelected = useCallback(
    async (
      e: React.ChangeEvent<HTMLInputElement>,
    ) => {
      const file = e.target.files?.[0]
      if (!file || !track) return
      setCoverBusy(true)
      try {
        const fd = new FormData()
        fd.append('cover', file)
        const up = await api.uploadTrackCover(
          track.id,
          fd,
        )
        if (up.cover_key) {
          setCoverKey(up.cover_key)
          setCoverVer((v) => v + 1)
          setCoverFailed(false)
          updateTrack(up)
        }
      } catch {}
      finally {
        setCoverBusy(false)
        e.target.value = ''
      }
    },
    [track, updateTrack],
  )

  const handleGenerate =
    useCallback(async () => {
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
            const u = await api.getTrack(track.id)
            if (
              u.cover_key &&
              u.cover_key !== coverKey
            ) {
              setCoverKey(u.cover_key)
              setCoverVer((v) => v + 1)
              setCoverFailed(false)
              break
            }
          } catch {}
        }
      } catch {}
      finally {
        setCoverBusy(false)
      }
    }, [track, genCooldown, coverKey])

  const handleRestoreCover =
    useCallback(async () => {
      if (!track) return
      setCoverBusy(true)
      try {
        const updated =
          await api.restoreTrackCover(track.id)
        if (updated.cover_key) {
          setCoverKey(updated.cover_key)
          setCoverVer((v) => v + 1)
          setCoverFailed(false)
          updateTrack(updated)
        }
      } catch {}
      finally {
        setCoverBusy(false)
      }
    }, [track, updateTrack])

  const handleVideoUpload = useCallback(
    () => videoInputRef.current?.click(),
    [],
  )

  const handleVideoSelected = useCallback(
    async (
      e: React.ChangeEvent<HTMLInputElement>,
    ) => {
      const file = e.target.files?.[0]
      if (!file || !track) return
      try {
        const fd = new FormData()
        fd.append('video', file)
        const updated = await api.uploadTrackVideo(
          track.id,
          fd,
        )
        updateTrack(updated)
        setVideoReady(false)
      } catch {}
      finally {
        e.target.value = ''
      }
    },
    [track, updateTrack],
  )

  const handleVideoDelete = useCallback(async () => {
    if (!track?.video_key) return
    try {
      await api.deleteTrackVideo(track.id)
      updateTrack({
        id: track.id,
        video_key: null,
      })
      setVideoReady(false)
    } catch {}
  }, [track, updateTrack])

  if (!isCardOpen || !track) return null

  const coverSrc = coverKey
    ? coverUrl(coverKey, coverVer)
    : null
  const videoSrc = track.video_key
    ? `/api/v1/tracks/${track.id}/video`
    : null
  const internalId = getInternalUserId()
  const isOwner =
    internalId !== null &&
    track.uploaded_by_id === internalId
  const liked = isLiked(track.id)
  const disliked = isDisliked(track.id)
  const pct = duration
    ? (currentTime / duration) * 100
    : 0

  const hasActiveVideo =
    !!videoSrc && videoEnabled
  const visualMode =
    showLyrics || hasActiveVideo

  return (
    <div
      className="tcs-backdrop"
      onClick={handleBackdrop}
    >
      <div
        className={`tcs-sheet${hasActiveVideo ? ' tcs-video-mode' : ''}`}
        ref={sheetRef}
      >
        <div className="tcs-handle" />
        <button
          className="tcs-close icon-btn"
          onClick={closeCard}
        >
          <Icon name="x" size={18} />
        </button>

        <div
          key={track.id}
          className="tcs-track-content"
        >
        {hasActiveVideo && (
          <>
            <video
              className="tcs-video-bg"
              src={videoSrc}
              autoPlay
              loop
              muted
              playsInline
              onCanPlay={() =>
                setVideoReady(true)
              }
              onError={() =>
                setVideoReady(false)
              }
            />
            <div className="tcs-video-gradient" />
          </>
        )}

        {hasActiveVideo && !videoReady && (
          <div className="tcs-video-standby">
            <Icon
              name="video"
              size={32}
              className="tcs-video-pulse"
            />
          </div>
        )}

        {hasActiveVideo &&
          videoReady &&
          !showLyrics && (
            <div className="tcs-video-spacer" />
          )}

        {!hasActiveVideo && !showLyrics && (
          <div
            className="tcs-cover-wrap"
            style={{ position: 'relative' }}
          >
            {coverBusy && (
              <div className="tcs-cover-loading">
                <div className="loader" />
              </div>
            )}
            {coverSrc && !coverFailed ? (
              <img
                className="tcs-cover"
                src={coverSrc}
                alt=""
                onError={() => setCoverFailed(true)}
              />
            ) : (
              <div className="tcs-cover-placeholder">
                <Icon name="music" size={72} />
              </div>
            )}
          </div>
        )}

        {showLyrics &&
          !editingLyrics &&
          !hasActiveVideo && (
            <div className="tcs-lyrics-section">
              <button
                className="tcs-lyrics-expand icon-btn"
                onClick={() => {
                  setShowLyrics(false)
                  openLyrics()
                }}
              >
                <Icon
                  name="maximize"
                  size={16}
                />
              </button>
              <LyricsPanel
                trackId={track.id}
                isOwner={isOwner}
                hasLyrics={
                  card?.has_lyrics ?? false
                }
                hasAudio={track.source === 'internal' || track.source === 'soundcloud'}
              />
            </div>
          )}

        {showLyrics &&
          !editingLyrics &&
          hasActiveVideo && (
            <div className="tcs-lyrics-section tcs-lyrics-over-video">
              <button
                className="tcs-lyrics-expand icon-btn"
                onClick={() => {
                  setShowLyrics(false)
                  openLyrics()
                }}
              >
                <Icon
                  name="maximize"
                  size={16}
                />
              </button>
              <LyricsPanel
                trackId={track.id}
                isOwner={isOwner}
                hasLyrics={
                  card?.has_lyrics ?? false
                }
                hasAudio={track.source === 'internal' || track.source === 'soundcloud'}
              />
            </div>
          )}

        <div className="tcs-info">
          {visualMode ? (
            <div className="tcs-info-cover-row">
              {coverSrc && (
                <img
                  className="tcs-info-cover-thumb"
                  src={coverSrc}
                  alt=""
                />
              )}
              <div className="tcs-info-cover-text">
                <h2 className="tcs-title">
                  {track.title}
                </h2>
                <p
                  className="tcs-artist"
                  onClick={() => {
                    if (
                      track.artist &&
                      onOpenArtist
                    ) {
                      closeCard()
                      onOpenArtist(track.artist)
                    }
                  }}
                  style={
                    track.artist
                      ? { cursor: 'pointer' }
                      : undefined
                  }
                >
                  {track.artist ?? '—'}
                </p>
              </div>
              <button
                className="icon-btn"
                onClick={handleShare}
              >
                <Icon name="link" size={18} />
              </button>
            </div>
          ) : (
            <>
              <div className="tcs-title-row">
                <h2 className="tcs-title">
                  {track.title}
                </h2>
                <button
                  className="icon-btn"
                  onClick={handleShare}
                >
                  <Icon
                    name="link"
                    size={18}
                  />
                </button>
              </div>
              <p
                className="tcs-artist"
                onClick={() => {
                  if (
                    track.artist &&
                    onOpenArtist
                  ) {
                    closeCard()
                    onOpenArtist(track.artist)
                  }
                }}
                style={
                  track.artist
                    ? { cursor: 'pointer' }
                    : undefined
                }
              >
                {track.artist ?? '—'}
              </p>
            </>
          )}
          <p className="tcs-meta">
            {track.catalog_type === 'ugc' &&
              'Каталог: пользовательская загрузка'}
            {track.catalog_type === 'licensed' &&
              'Каталог: лицензированный материал'}
            {track.catalog_type ===
              'external_reference' &&
              'Каталог: внешний reference'}
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
                  />
                ) : (
                  <Icon
                    name="user"
                    size={18}
                  />
                )}
              </div>
              <span className="tcs-author-name">
                {card.author.display_name ||
                  card.author.username ||
                  'Автор'}
              </span>
              <Icon
                name="chevron"
                size={16}
                className="tcs-author-chevron"
              />
            </div>
          )}
        </div>
        </div>

        <div className="tcs-player-controls">
          <div className="tcs-seek-wrap">
            <input
              type="range"
              className="tcs-seek"
              min={0}
              max={100}
              step={0.1}
              value={pct}
              onChange={(e) =>
                seek(Number(e.target.value))
              }
            />
            <div className="tcs-time">
              <span>{fmt(currentTime)}</span>
              <span>{fmt(duration)}</span>
            </div>
          </div>
          <div className="tcs-play-row">
            <button
              className="ctrl-btn"
              onClick={playPrev}
            >
              <Icon
                name="skip-back"
                size={22}
              />
            </button>
            <button
              className="play-btn"
              onClick={togglePlay}
            >
              <Icon
                name={
                  isPlaying ? 'pause' : 'play'
                }
                size={20}
              />
            </button>
            <button
              className="ctrl-btn"
              onClick={playNext}
            >
              <Icon
                name="skip-forward"
                size={22}
              />
            </button>
          </div>
        </div>

        <div
          className={`tcs-actions${editingLyrics ? ' tcs-dimmed' : ''}`}
        >
          <button
            className={`tcs-action-btn${liked ? ' active' : ''}`}
            onClick={() => toggleLike(track.id)}
          >
            <Icon
              name={
                liked ? 'heart' : 'heart-outline'
              }
              size={20}
            />
            <span className="tcs-action-label">
              Лайк
            </span>
          </button>

          <button
            className={`tcs-action-btn${disliked ? ' active' : ''}`}
            onClick={() =>
              toggleDislike(track.id)
            }
          >
            <Icon
              name="thumbs-down"
              size={20}
            />
            <span className="tcs-action-label">
              Дизлайк
            </span>
          </button>

          <button
            className={`tcs-action-btn${showLyrics ? ' active' : ''}`}
            onClick={() => {
              setShowLyrics((v) => !v)
              setEditingLyrics(false)
            }}
            disabled={
              !card?.has_lyrics && !isOwner
            }
          >
            <Icon name="text" size={20} />
            <span className="tcs-action-label">
              Текст
            </span>
          </button>

          <button
            className="tcs-action-btn"
            onClick={handleAuthor}
            disabled={!card?.author}
          >
            <Icon name="user" size={20} />
            <span className="tcs-action-label">
              К автору
            </span>
          </button>

          {isOwner && (
            <button
              className={`tcs-action-btn${showEdit ? ' active' : ''}`}
              onClick={() =>
                setShowEdit((v) => !v)
              }
            >
              <Icon name="edit" size={20} />
              <span className="tcs-action-label">
                Редактировать
              </span>
            </button>
          )}


          <button
            className="tcs-action-btn"
            onClick={openComplaint}
          >
            <Icon name="flag" size={20} />
            <span className="tcs-action-label">
              Жалоба
            </span>
          </button>
        </div>

        {showEdit && isOwner && (
          <div className="tcs-edit-panel">
            <div className="tcs-edit-title">
              Редактирование
            </div>
            <div className="tcs-edit-actions">
              {track.source === 'internal' && (
                <>
                  <button
                    className="tcs-edit-btn"
                    onClick={handleCoverUpload}
                    disabled={coverBusy}
                  >
                    <Icon
                      name="image"
                      size={18}
                    />
                    Обложка
                  </button>
                  <button
                    className="tcs-edit-btn"
                    onClick={handleGenerate}
                    disabled={
                      coverBusy || genCooldown > 0
                    }
                  >
                    <Icon
                      name="sparkle"
                      size={18}
                    />
                    {genCooldown > 0
                      ? `${genCooldown}с`
                      : 'Генерация'}
                  </button>
                </>
              )}
              {track.source === 'soundcloud' && (
                <button
                  className="tcs-edit-btn"
                  onClick={handleRestoreCover}
                  disabled={coverBusy}
                >
                  <Icon
                    name="image"
                    size={18}
                  />
                  Восстановить обложку
                </button>
              )}
              <button
                className={`tcs-edit-btn${editingLyrics ? ' active' : ''}`}
                onClick={() => {
                  setEditingLyrics((v) => !v)
                }}
              >
                <Icon
                  name="text"
                  size={18}
                />
                Текст
              </button>
              <button
                className="tcs-edit-btn"
                onClick={handleVideoUpload}
              >
                <Icon
                  name="video"
                  size={18}
                />
                Видео
              </button>
              {track.video_key && (
                <button
                  className="tcs-edit-btn"
                  onClick={handleVideoDelete}
                >
                  <Icon
                    name="x"
                    size={18}
                  />
                  Удалить видео
                </button>
              )}
            </div>
          </div>
        )}

        {editingLyrics && isOwner && (
          <div className="tcs-lyrics-edit-inline">
            <LyricsPanel
              trackId={track.id}
              isOwner={isOwner}
              hasLyrics={
                card?.has_lyrics ?? false
              }
              hasAudio={track.source === 'internal' || track.source === 'soundcloud'}
              forceEdit
            />
            <button
              className="tcs-lyrics-edit-close"
              onClick={() =>
                setEditingLyrics(false)
              }
            >
              <Icon name="x" size={16} />
              Закрыть редактор
            </button>
          </div>
        )}

        {(track.source_url || track.sc_url) && (
          <div className="tcs-source-info">
            <span className="tcs-source-label">
              Источник:{' '}
              <a
                href={track.source_url || track.sc_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
              >
                {track.source_name || track.source}
              </a>
            </span>
            <p className="tcs-disclaimer">
              {track.access_mode === 'third_party_stream'
                ? 'Внешний трек: аудиофайл не хранится в хранилище DotSound. Воспроизведение выполняется через поток стороннего сервиса внутри интерфейса DotSound. Правообладатель может направить уведомление через форму жалобы.'
                : 'Внешний трек: DotSound хранит метаданные и ссылку на оригинальный источник, но не размещает этот аудиофайл в собственном хранилище. Правообладатель может направить уведомление через форму жалобы.'}
            </p>
          </div>
        )}

        {similarTracks.length > 0 && (
          <div className="tcs-similar-section">
            <h3 className="tcs-similar-title">Похожие треки</h3>
            <div className="tcs-similar-list">
              {similarTracks.slice(0, 5).map((st) => (
                <div
                  key={st.id}
                  className="tcs-similar-item"
                  onClick={() => {
                    closeCard()
                    playTrack(st)
                  }}
                >
                  <CoverImage coverKey={st.cover_key} />
                  <div className="tcs-similar-info">
                    <span className="tcs-similar-track-title">{st.title}</span>
                    <span className="tcs-similar-track-artist">{st.artist ?? '—'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="tcs-volume-section">
          <Icon
            name={
              volume === 0
                ? 'volume-off'
                : volume < 0.5
                  ? 'volume-low'
                  : 'volume-high'
            }
            size={16}
            className="tcs-volume-icon"
          />
          <input
            type="range"
            className="tcs-volume"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(e) =>
              setVolume(
                parseFloat(e.target.value),
              )
            }
          />
        </div>

        <input
          ref={coverInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: 'none' }}
          onChange={handleCoverSelected}
        />
        <input
          ref={videoInputRef}
          type="file"
          accept="video/mp4,video/webm"
          style={{ display: 'none' }}
          onChange={handleVideoSelected}
        />

        {loading && !card && (
          <div className="tcs-loader">
            <div className="loader" />
          </div>
        )}
      </div>
    </div>
  )
}
