import {
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import { getInternalUserId } from '@/lib/telegram'
import { api } from '@/lib/api'
import { showIsland } from '@/lib/island'
import { LongPressMenu } from '@/components/ui/LongPressMenu'
import type { LongPressMenuItem } from '@/components/ui/LongPressMenu'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { SharedCover } from '@/components/ui/SharedCover'
import { BeatPulse } from '@/components/ui/BeatPulse'
import type { Track } from '@/types/api'

interface Props {
  track: Track
  variant?: 'compact' | 'expanded'
  onDeleted?: (trackId: number) => void
  onVisibilityChanged?: (track: Track) => void
}

function fmtDuration(sec: number | null): string {
  if (!sec) return ''
  const mins = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${mins}:${s}`
}

function getCatalogLabel(track: Track): string | null {
  if (track.catalog_type === 'external_reference') return 'EXT'
  if (track.catalog_type === 'licensed') return 'LIC'
  if (track.catalog_type === 'ugc') return 'UGC'
  return null
}

export function TrackCard({
  track,
  variant = 'compact',
  onDeleted,
  onVisibilityChanged,
}: Props) {
  const { t } = useTranslation()
  const { isLiked, toggleLike } = useLikes()
  const { track: currentTrack } = usePlayerMeta()
  const { isPlaying } = usePlayerState()
  const { playTrack, addToQueue } = usePlayerActions()
  const [confirmingDelete, setConfirmingDelete] =
    useState(false)
  const confirmTimerRef = useRef<ReturnType<
    typeof setTimeout
  > | null>(null)

  const isCurrentTrack =
    currentTrack?.id === track.id
  const isTrackPlaying = isCurrentTrack && isPlaying
  const liked = isLiked(track.id)
  const internalId = getInternalUserId()
  const isOwner =
    internalId !== null &&
    track.uploaded_by_id === internalId
  const catalogLabel = getCatalogLabel(track)
  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null
  const trackBpm = (
    track as unknown as { bpm?: number }
  ).bpm
  const pulseBpm =
    typeof trackBpm === 'number' ? trackBpm : 120

  const menuItems = useMemo((): LongPressMenuItem[] => {
    const items: LongPressMenuItem[] = [
      {
        id: 'like',
        label: liked
          ? t('redesign.tracks.unlike', 'Unlike')
          : t('redesign.tracks.like', 'Like'),
        icon: 'heart',
        onPick: () => {
          void toggleLike(track.id)
        },
      },
      {
        id: 'queue',
        label: t(
          'redesign.tracks.addQueue',
          'Add to queue',
        ),
        icon: 'queue',
        onPick: () => {
          addToQueue(track)
          showIsland({
            kind: 'toast',
            title: t('redesign.tracks.longPressQueued', 'Added to queue'),
            durationMs: 2000,
          })
        },
      },
      {
        id: 'share',
        label: t('redesign.tracks.share', 'Share'),
        icon: 'share-arrow',
        onPick: async () => {
          const url = `${window.location.origin}/mini_app/track/${track.id}`
          try {
            if (navigator.share) {
              await navigator.share({
                title: track.title,
                url,
              })
            } else {
              await navigator.clipboard.writeText(url)
            }
          } catch {
            showIsland({
              kind: 'error',
              title: t('redesign.tracks.shareFail', 'Could not share'),
              durationMs: 3500,
            })
          }
        },
      },
    ]
    if (isOwner && onVisibilityChanged) {
      items.push({
        id: 'visibility',
        label: track.is_public
          ? t(
              'redesign.tracks.makePrivate',
              'Make private',
            )
          : t(
              'redesign.tracks.makePublic',
              'Make public',
            ),
        icon: track.is_public ? 'lock' : 'eye',
        onPick: async () => {
          try {
            const updated = await api.updateTrack(
              track.id,
              { is_public: !track.is_public },
            )
            onVisibilityChanged(updated)
          } catch {
            /* ignore */
          }
        },
      })
    }
    return items
  }, [
    liked,
    t,
    track,
    isOwner,
    onVisibilityChanged,
    addToQueue,
    toggleLike,
  ])

  const handleClick = () => {
    playTrack(track)
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
      confirmTimerRef.current = setTimeout(
        () => setConfirmingDelete(false),
        3000,
      )
      return
    }
    if (confirmTimerRef.current)
      clearTimeout(confirmTimerRef.current)
    setConfirmingDelete(false)
    try {
      await api.deleteTrack(track.id)
      onDeleted?.(track.id)
    } catch {
      /* ignore */
    }
  }

  const handleToggleVisibility = async (
    e: MouseEvent,
  ) => {
    e.stopPropagation()
    if (!internalId) return
    try {
      const updated = await api.updateTrack(
        track.id,
        { is_public: !track.is_public },
      )
      onVisibilityChanged?.(updated)
    } catch {
      /* ignore */
    }
  }

  const rowClass =
    variant === 'expanded'
      ? 'track-card-main-row re-tc-main re-tc-main--expanded'
      : 'track-card-main-row re-tc-main'

  return (
    <LongPressMenu items={menuItems}>
      <div
        className={`track-card re-tc-card${isCurrentTrack ? ' playing' : ''}${variant === 'expanded' ? ' track-card--expanded' : ''}`}
        data-id={track.id}
        onClick={handleClick}
        role="button"
      >
        <div className={rowClass}>
          <div
            className={`re-tc-cover-wrap${isTrackPlaying ? ' is-playing' : ''}`}
          >
            {coverSrc ? (
              <BeatPulse
                bpm={pulseBpm}
                active={isTrackPlaying}
              >
                <SharedCover
                  trackId={track.id}
                  src={coverSrc}
                  alt=""
                  className="re-tc-cover"
                />
              </BeatPulse>
            ) : (
              <div className="re-tc-cover-fallback">
                <Icon name="music" size={20} />
              </div>
            )}
          </div>
          <div className="track-card-info">
            <div className="track-card-title-row">
              <p className="track-card-title" dir="auto">
                {track.title}
              </p>
              {!track.is_public && (
                <span className="track-badge track-badge-private">
                  <Icon name="lock" size={12} />
                </span>
              )}
              {isOwner && !track.is_active && (
                <span
                  className="track-badge track-badge-hidden"
                  title={t('trackCard.hiddenByMod')}
                >
                  MOD
                </span>
              )}
              {track.source === 'soundcloud' && (
                <span className="track-badge track-badge-sc">
                  SC
                </span>
              )}
              {track.source === 'youtube' && (
                <span className="track-badge track-badge-yt">
                  YT
                </span>
              )}
              {track.source === 'bandcamp' && (
                <span className="track-badge track-badge-bc">
                  BC
                </span>
              )}
              {track.source === 'telegram' && (
                <span className="track-badge track-badge-tg">
                  TG
                </span>
              )}
              {catalogLabel && (
                <span className="track-badge">
                  {catalogLabel}
                </span>
              )}
            </div>
            <p className="track-card-artist" dir="auto">
              {track.artist ?? t('trackCard.unknownArtist')}
            </p>
            <p className="track-card-meta">
              <Icon name="play" size={11} className="meta-icon" />{' '}
              {track.play_count}
              {track.duration_seconds
                ? ` · ${fmtDuration(track.duration_seconds)}`
                : ''}
            </p>
            {(track.source_url || track.sc_url) && (
              <span className="track-source">
                {t('search.extSourceLabel')}{' '}
                <a
                  href={
                    track.source_url ||
                    track.sc_url ||
                    '#'
                  }
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
              <span className="track-source">
                {t('trackCard.accessStream')}
              </span>
            )}
            {track.catalog_type === 'ugc' && (
              <span className="track-source">
                {t('trackCard.catUgc')}
              </span>
            )}
            {track.catalog_type === 'licensed' && (
              <span className="track-source">
                {t('trackCard.catLicensed')}
              </span>
            )}
            {track.catalog_type === 'external_reference' && (
              <span className="track-source">
                {t('trackCard.catRef')}
              </span>
            )}
            {!track.source_url &&
              !track.sc_url &&
              track.source === 'telegram' && (
                <span className="track-source">
                  {t('trackCard.sourceTg')}
                </span>
              )}
          </div>
          <div
            className="track-card-actions"
            onClick={(e) => e.stopPropagation()}
          >
            <MotionPress
              variant="icon"
              className={`track-card-like${liked ? ' liked spring' : ''}`}
              title={t('trackCard.like')}
              ariaLabel={
                liked
                  ? t('trackCard.unlike')
                  : t('trackCard.like')
              }
              aria-pressed={liked}
              haptic="light"
              onClick={handleLike}
            >
              <MorphIcon
                name="heart"
                filled={liked}
                size={18}
              />
            </MotionPress>
            {isOwner && (
              <>
                <button
                  className="track-card-visibility"
                  title={
                    track.is_public
                      ? t('trackCard.private')
                      : t('trackCard.public')
                  }
                  type="button"
                  onClick={handleToggleVisibility}
                >
                  <Icon
                    name={
                      track.is_public ? 'eye' : 'lock'
                    }
                    size={16}
                  />
                </button>
                <button
                  className={`track-card-delete${confirmingDelete ? ' danger' : ''}`}
                  title={
                    confirmingDelete
                      ? t('trackCard.deleteConfirm')
                      : t('trackCard.delete')
                  }
                  type="button"
                  onClick={handleDelete}
                >
                  <Icon
                    name={
                      confirmingDelete ? 'check' : 'trash'
                    }
                    size={16}
                  />
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </LongPressMenu>
  )
}

