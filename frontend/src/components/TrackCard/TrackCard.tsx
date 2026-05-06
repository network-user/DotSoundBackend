import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { getInternalUserId, haptic } from '@/lib/telegram'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/Toast'
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
  const { t } = useTranslation()
  const { isLiked, toggleLike } = useLikes()
  const { track: currentTrack } = usePlayerMeta()
  const { playTrack, addToQueue } = usePlayerActions()
  const toast = useToast()
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [showInfo, setShowInfo] = useState(false)
  const [trackInfo, setTrackInfo] = useState<TrackInfoResponse | null>(null)
  const [loadingInfo, setLoadingInfo] = useState(false)
  
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressFiredRef = useRef(false)

  useEffect(() => {
    if (showInfo && !trackInfo && !loadingInfo) {
      setLoadingInfo(true)
      api.getTrackInfo(track.id)
        .then(setTrackInfo)
        .finally(() => setLoadingInfo(false))
    }
  }, [showInfo, track.id, trackInfo, loadingInfo])

  const handlePointerDown = () => {
    longPressFiredRef.current = false
    longPressTimerRef.current = setTimeout(() => {
      longPressFiredRef.current = true
      haptic('medium')
      addToQueue(track)
      toast.success(t('trackCard.queued'))
    }, 550)
  }

  const handlePointerUp = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }

  const handleClick = () => {
    if (longPressFiredRef.current) return
    playTrack(track)
  }

  const playing = currentTrack?.id === track.id
  const liked = isLiked(track.id)
  const internalId = getInternalUserId()
  const isOwner = internalId !== null && track.uploaded_by_id === internalId
  const catalogLabel = getCatalogLabel(track)

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    await toggleLike(track.id)
  }

  const handleToggleInfo = (e: MouseEvent) => {
    e.stopPropagation()
    setShowInfo(!showInfo)
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
      className={`track-card${playing ? ' playing' : ''}${showInfo ? ' info-expanded' : ''}`}
      data-id={track.id}
      onClick={handleClick}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      <div className="track-card-main-row">
        <CoverImage coverKey={track.cover_key} />
        <div className="track-card-info">
          <div className="track-card-title-row">
            <p className="track-card-title" dir="auto">{track.title}</p>
            {!track.is_public && (
              <span className="track-badge track-badge-private"><Icon name="lock" size={12} /></span>
            )}
            {isOwner && !track.is_active && (
              <span
                className="track-badge track-badge-hidden"
                title={t('trackCard.hiddenByMod')}
              >
                MOD
              </span>
            )}
          </div>
          <p className="track-card-artist" dir="auto">
            {track.artist ?? t('trackCard.unknownArtist')}
          </p>
          <p className="track-card-meta">
            <Icon name="play" size={11} className="meta-icon" />
            {' '}{track.play_count}
            {track.duration_seconds ? ` · ${fmtDuration(track.duration_seconds)}` : ''}
          </p>
        </div>
        <div className="track-card-actions" onClick={(e) => e.stopPropagation()}>
          <button
            className={`track-card-info-btn${showInfo ? ' active' : ''}`}
            title={t('trackCard.info')}
            onClick={handleToggleInfo}
          >
            <Icon name="info" size={18} />
          </button>
          <button
            className={`track-card-like${liked ? ' liked spring' : ''}`}
            title={t('trackCard.like')}
            aria-label={
              liked
                ? t('trackCard.unlike')
                : t('trackCard.like')
            }
            aria-pressed={liked}
            onClick={handleLike}
          >
            <Icon name={liked ? 'heart' : 'heart-outline'} size={18} />
          </button>
          {isOwner && (
            <>
              <button
                className="track-card-visibility"
                title={
                  track.is_public
                    ? t('trackCard.private')
                    : t('trackCard.public')
                }
                onClick={handleToggleVisibility}
              >
                <Icon name={track.is_public ? 'eye' : 'lock'} size={16} />
              </button>
              <button
                className={`track-card-delete${confirmingDelete ? ' danger' : ''}`}
                title={
                  confirmingDelete
                    ? t('trackCard.deleteConfirm')
                    : t('trackCard.delete')
                }
                onClick={handleDelete}
              >
                <Icon name={confirmingDelete ? 'check' : 'trash'} size={16} />
              </button>
            </>
          )}
        </div>
      </div>

      {showInfo && (
        <div className="track-card-ai-body" onClick={(e) => e.stopPropagation()}>
          <div className="track-card-badges-row">
            {track.source === 'soundcloud' && <span className="track-badge track-badge-sc">SC</span>}
            {track.source === 'youtube' && <span className="track-badge track-badge-yt">YT</span>}
            {track.source === 'bandcamp' && <span className="track-badge track-badge-bc">BC</span>}
            {track.source === 'telegram' && <span className="track-badge track-badge-tg">TG</span>}
            {catalogLabel && <span className="track-badge">{catalogLabel}</span>}
          </div>

          {(track.source_url || track.sc_url) && (
            <div className="track-source">
              {t('search.extSourceLabel')}{' '}
              <a
                href={track.source_url || track.sc_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="track-source-link"
              >
                {track.source_name || track.source}
              </a>
            </div>
          )}
          {track.access_mode === 'third_party_stream' && (
            <div className="track-source">
              {t('trackCard.accessStream')}
            </div>
          )}
          {track.catalog_type === 'ugc' && (
            <div className="track-source">
              {t('trackCard.catUgc')}
            </div>
          )}
          {track.catalog_type === 'licensed' && (
            <div className="track-source">
              {t('trackCard.catLicensed')}
            </div>
          )}
          {track.catalog_type === 'external_reference' && (
            <div className="track-source">
              {t('trackCard.catRef')}
            </div>
          )}
          {!track.source_url && !track.sc_url && track.source === 'telegram' && (
            <div className="track-source">
              {t('trackCard.sourceTg')}
            </div>
          )}

          {loadingInfo && (
            <p className="track-card-ai-info-loading">{t('trackSheet.preparingInfo')}</p>
          )}
          {trackInfo?.content && (
            <p className="track-card-ai-text">{trackInfo.content}</p>
          )}
        </div>
      )}
    </div>
  )
}

