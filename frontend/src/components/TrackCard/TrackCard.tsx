import { useRef, useState, useEffect, type MouseEvent } from 'react'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { getInternalUserId } from '@/lib/telegram'
import { api } from '@/lib/api'
import type { Track, TrackInfoResponse } from '@/types/api'

interface Props {
  track: Track
  onDeleted?: (trackId: number) => void
  onVisibilityChanged?: (track: Track) => void
}

function fmtDuration(sec: number | null): string {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function getCatalogLabel(track: Track): string | null {
  if (track.catalog_type === 'external_reference') return 'EXT'
  if (track.catalog_type === 'licensed') return 'LIC'
  if (track.catalog_type === 'ugc') return 'UGC'
  return null
}

export function TrackCard({ track, onDeleted, onVisibilityChanged }: Props) {
  const { isLiked, toggleLike } = useLikes()
  const { track: currentTrack } = usePlayerMeta()
  const { playTrack } = usePlayerActions()
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [infoOpen, setInfoOpen] = useState(false)
  const [trackInfo, setTrackInfo] = useState<TrackInfoResponse | null>(null)
  const [infoLoading, setInfoLoading] = useState(false)
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const playing = currentTrack?.id === track.id
  const liked = isLiked(track.id)
  const internalId = getInternalUserId()
  const isOwner = internalId !== null && track.uploaded_by_id === internalId
  const catalogLabel = getCatalogLabel(track)

  useEffect(() => {
    return () => { if (pollRef.current) clearTimeout(pollRef.current) }
  }, [])

  async function handleInfoClick(e: MouseEvent) {
    e.stopPropagation()
    if (infoOpen) { setInfoOpen(false); return }
    setInfoOpen(true)
    if (trackInfo?.status === 'done') return
    await loadInfo()
  }

  async function loadInfo(attempt = 0) {
    setInfoLoading(true)
    try {
      const info = await api.getTrackInfo(track.id)
      setTrackInfo(info)
      if ((info.status === 'fetching' || info.status === 'pending') && attempt < 20) {
        pollRef.current = setTimeout(() => loadInfo(attempt + 1), 3000)
      } else {
        setInfoLoading(false)
      }
    } catch {
      setInfoLoading(false)
    }
  }

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    await toggleLike(track.id)
  }

  const handleDelete = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!internalId) return
    if (!confirmingDelete) {
      setConfirmingDelete(true)
      confirmTimerRef.current = setTimeout(() => setConfirmingDelete(false), 3000)
      return
    }
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current)
    setConfirmingDelete(false)
    try {
      await api.deleteTrack(track.id)
      onDeleted?.(track.id)
    } catch { }
  }

  const handleToggleVisibility = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!internalId) return
    try {
      const updated = await api.updateTrack(track.id, { is_public: !track.is_public })
      onVisibilityChanged?.(updated)
    } catch { }
  }

  return (
    <div
      className={`track-card${playing ? ' playing' : ''}`}
      data-id={track.id}
      onClick={() => playTrack(track)}
    >
      <div className="track-card-main-row">
        <CoverImage coverKey={track.cover_key} />
        <div className="track-card-info">
          <div className="track-card-title-row">
            <p className="track-card-title">{track.title}</p>
            {!track.is_public && (
              <span className="track-badge track-badge-private"><Icon name="lock" size={12} /></span>
            )}
            {track.source === 'soundcloud' && <span className="track-badge track-badge-sc">SC</span>}
            {track.source === 'telegram' && <span className="track-badge track-badge-tg">TG</span>}
            {catalogLabel && <span className="track-badge">{catalogLabel}</span>}
          </div>
          <p className="track-card-artist">{track.artist ?? 'Неизвестный исполнитель'}</p>
          <p className="track-card-meta">
            <Icon name="play" size={11} className="meta-icon" />
            {' '}{track.play_count}
            {track.duration_seconds ? ` · ${fmtDuration(track.duration_seconds)}` : ''}
          </p>
          {(track.source_url || track.sc_url) && (
            <span className="track-source">
              внешний источник:{' '}
              <a
                href={track.source_url || track.sc_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="track-source-link"
                onClick={(e) => e.stopPropagation()}
              >
                {track.source_name || track.source}
              </a>
            </span>
          )}
          {track.access_mode === 'third_party_stream' && (
            <span className="track-source">режим доступа: внешний поток стороннего сервиса</span>
          )}
          {track.catalog_type === 'ugc' && (
            <span className="track-source">тип каталога: пользовательская загрузка</span>
          )}
          {track.catalog_type === 'licensed' && (
            <span className="track-source">тип каталога: лицензированный материал</span>
          )}
          {track.catalog_type === 'external_reference' && (
            <span className="track-source">тип каталога: внешний reference</span>
          )}
          {!track.source_url && !track.sc_url && track.source === 'telegram' && (
            <span className="track-source">источник: Telegram</span>
          )}
        </div>
        <div className="track-card-actions" onClick={(e) => e.stopPropagation()}>
          <button
            className={`track-card-like${liked ? ' liked spring' : ''}`}
            title="Лайк"
            aria-label={liked ? 'Убрать лайк' : 'Поставить лайк'}
            aria-pressed={liked}
            onClick={handleLike}
          >
            <Icon name={liked ? 'heart' : 'heart-outline'} size={18} />
          </button>
          {isOwner && (
            <>
              <button
                className="track-card-visibility"
                title={track.is_public ? 'Сделать приватным' : 'Сделать публичным'}
                onClick={handleToggleVisibility}
              >
                <Icon name={track.is_public ? 'eye' : 'lock'} size={16} />
              </button>
              <button
                className={`track-card-delete${confirmingDelete ? ' danger' : ''}`}
                title={confirmingDelete ? 'Нажмите ещё раз для удаления' : 'Удалить трек'}
                onClick={handleDelete}
              >
                <Icon name={confirmingDelete ? 'check' : 'trash'} size={16} />
              </button>
            </>
          )}
        </div>
      </div>

      <div className="track-card-footer" onClick={(e) => e.stopPropagation()}>
        <button
          className={`track-card-info-row-btn${infoOpen ? ' active' : ''}`}
          onClick={handleInfoClick}
        >
          <Icon name="info" size={13} />
          {infoLoading && (!trackInfo || trackInfo.status !== 'done')
            ? 'Загрузка…'
            : infoOpen ? 'Скрыть' : 'Информация'}
        </button>
      </div>

      {infoOpen && (
        <div className="track-card-ai-body" onClick={(e) => e.stopPropagation()}>
          {infoLoading && (!trackInfo || trackInfo.status !== 'done') && (
            <p className="track-card-ai-info-loading">Запрашиваем информацию о треке…</p>
          )}
          {trackInfo?.status === 'done' && trackInfo.content && (
            <p className="track-card-ai-text">{trackInfo.content}</p>
          )}
          {trackInfo?.status === 'not_found' && (
            <p className="track-card-ai-info-loading">Информация не найдена</p>
          )}
          {trackInfo?.status === 'failed' && (
            <p className="track-card-ai-info-loading">Ошибка загрузки</p>
          )}
        </div>
      )}
    </div>
  )
}
