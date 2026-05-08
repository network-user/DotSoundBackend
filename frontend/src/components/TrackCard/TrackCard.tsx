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
import { buildTrackCardSummaryLine } from '@/lib/trackCardFormat'
import { useDesktopFinePointer } from '@/hooks/useDesktopFinePointer'
import { useNavigateToArtistByName } from '@/hooks/useNavigateToArtistByName'

interface Props {
  track: Track
  variant?: 'compact' | 'expanded'
  summarySuffix?: string | null
  onDeleted?: (trackId: number) => void
  onVisibilityChanged?: (track: Track) => void
}

export function TrackCard({
  track,
  variant = 'compact',
  summarySuffix = null,
  onDeleted,
  onVisibilityChanged,
}: Props) {
  const { t } = useTranslation()
  const { isLiked, toggleLike } = useLikes()
  const { track: currentTrack } = usePlayerMeta()
  const { isPlaying } = usePlayerState()
  const { playTrack, addToQueue } = usePlayerActions()
  const desktopFine = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()
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
          ? t('redesign.tracks.unlike')
          : t('redesign.tracks.like'),
        icon: 'heart',
        onPick: () => {
          void toggleLike(track.id)
        },
      },
      {
        id: 'queue',
        label: t(
          'redesign.tracks.addQueue',
        ),
        icon: 'queue',
        onPick: () => {
          addToQueue(track)
          showIsland({
            kind: 'toast',
            title: t('redesign.tracks.longPressQueued'),
            durationMs: 2000,
          })
        },
      },
      {
        id: 'share',
        label: t('redesign.tracks.share'),
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
              title: t('redesign.tracks.shareFail'),
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
                <Icon name="music" size={22} />
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
            </div>
            {track.artist ? (
              <p
                className={
                  desktopFine
                    ? 'track-card-artist track-card-artist--nav'
                    : 'track-card-artist'
                }
                dir="auto"
                style={
                  desktopFine
                    ? { cursor: 'pointer' }
                    : undefined
                }
                onClick={
                  desktopFine
                    ? (e) => {
                        e.stopPropagation()
                        void goArtistByName(track.artist)
                      }
                    : undefined
                }
              >
                {track.artist}
              </p>
            ) : null}
            <p className="track-card-meta track-card-summary" dir="auto">
              {buildTrackCardSummaryLine(
                track,
                t,
                summarySuffix,
              )}
            </p>
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
                size={20}
              />
            </MotionPress>
            {isOwner && (
              <>
                <MotionPress
                  variant="icon"
                  className="track-card-visibility"
                  title={
                    track.is_public
                      ? t('trackCard.private')
                      : t('trackCard.public')
                  }
                  ariaLabel={
                    track.is_public
                      ? t('trackCard.private')
                      : t('trackCard.public')
                  }
                  haptic="light"
                  onClick={handleToggleVisibility}
                >
                  <Icon
                    name={
                      track.is_public ? 'eye' : 'lock'
                    }
                    size={20}
                  />
                </MotionPress>
                <MotionPress
                  variant="icon"
                  className={`track-card-delete${confirmingDelete ? ' danger' : ''}`}
                  title={
                    confirmingDelete
                      ? t('trackCard.deleteConfirm')
                      : t('trackCard.delete')
                  }
                  ariaLabel={
                    confirmingDelete
                      ? t('trackCard.deleteConfirm')
                      : t('trackCard.delete')
                  }
                  haptic="medium"
                  onClick={handleDelete}
                >
                  <Icon
                    name={
                      confirmingDelete ? 'check' : 'trash'
                    }
                    size={20}
                  />
                </MotionPress>
              </>
            )}
          </div>
        </div>
      </div>
    </LongPressMenu>
  )
}

