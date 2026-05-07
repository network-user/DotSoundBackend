import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  LongPressMenu,
  type LongPressMenuItem,
} from '@/components/ui/LongPressMenu'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { VoicePlayer } from '@/components/Chat/VoicePlayer'
import { api } from '@/lib/api'
import { useBrandLabel } from '@/lib/brand'
import { usePlayerActions } from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { useDesktopFinePointer } from '@/hooks/useDesktopFinePointer'
import { useNavigateToArtistByName } from '@/hooks/useNavigateToArtistByName'
import {
  m,
  SPRING_BOUNCY,
  SPRING_GENTLE,
  useReducedMotion,
} from '@/lib/motion'
import type {
  AlbumWithTracksRecord,
  ChatMessage,
  PlaylistWithTracks,
  Track,
} from '@/types/api'

interface Props {
  message: ChatMessage & {
    _uploading?: boolean
    is_system?: boolean
    sender_role?: 'admin' | 'user' | 'system'
  }
  isMine: boolean
  onDelete: (id: number) => void
  onReaction: (id: number, type: string) => void
  onCancelUpload?: () => void
  onViewPhoto?: (src: string) => void
}

interface ReactionItem {
  type: string
  icon: string
  labelKey: string
}

const REACTION_ITEMS: ReactionItem[] = [
  { type: 'heart', icon: 'heart', labelKey: 'redesign.chats.reactionHeart' },
  { type: 'thumbs-up', icon: 'thumbs-up', labelKey: 'redesign.chats.reactionLike' },
  { type: 'flame', icon: 'flame', labelKey: 'redesign.chats.reactionFire' },
  { type: 'sparkle', icon: 'sparkle', labelKey: 'redesign.chats.reactionWow' },
  { type: 'music', icon: 'music', labelKey: 'redesign.chats.reactionMusic' },
  { type: 'star', icon: 'star', labelKey: 'redesign.chats.reactionStar' },
]
const SHARED_TRACK_CACHE = new Map<number, Track>()
const SHARED_ALBUM_CACHE =
  new Map<number, AlbumWithTracksRecord>()
const SHARED_PLAYLIST_CACHE =
  new Map<number, PlaylistWithTracks>()

export function ChatBubble({
  message,
  isMine,
  onDelete,
  onReaction,
  onCancelUpload,
  onViewPhoto,
}: Props) {
  const { t } = useTranslation()
  const brandLabel = useBrandLabel()
  const reduce = useReducedMotion()
  const [imgLoaded, setImgLoaded] = useState(false)
  const [sharedTrack, setSharedTrack] = useState<Track | null>(null)
  const [sharedTrackLoading, setSharedTrackLoading] = useState(false)
  usePrefetchTracks(
    sharedTrack ? [sharedTrack] : null,
    'chat_shared',
    { additive: true },
  )
  const [sharedAlbum, setSharedAlbum] =
    useState<AlbumWithTracksRecord | null>(null)
  const [sharedAlbumLoading, setSharedAlbumLoading] =
    useState(false)
  const [sharedPlaylist, setSharedPlaylist] =
    useState<PlaylistWithTracks | null>(null)
  const [sharedPlaylistLoading, setSharedPlaylistLoading] =
    useState(false)
  const { playTrack } = usePlayerActions()
  const desktopFineNav = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()

  const photoAtt = message.attachments?.find(
    (a) => a.file_type === 'photo',
  )
  const voiceAtt = message.attachments?.find(
    (a) => a.file_type === 'voice',
  )

  const isLocal =
    photoAtt?.file_key?.startsWith('blob:')
  const photoSrc = isLocal
    ? photoAtt!.file_key
    : photoAtt
      ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(photoAtt.file_key)}`
      : ''

  const handlePhotoClick = () => {
    if (
      message._uploading ||
      !imgLoaded ||
      !photoSrc
    )
      return
    onViewPhoto?.(photoSrc)
  }

  const isSystem =
    message.is_system === true ||
    message.sender_role === 'admin' ||
    message.sender_role === 'system'

  const menuItems = useMemo<LongPressMenuItem[]>(() => {
    if (message._uploading) return []
    const reactionItems: LongPressMenuItem[] = REACTION_ITEMS.map(
      (r) => ({
        id: `react-${r.type}`,
        label: t(r.labelKey),
        icon: r.icon,
        onPick: () => onReaction(message.id, r.type),
      }),
    )
    if (isMine) {
      reactionItems.push({
        id: 'delete',
        label: t('redesign.chats.deleteMessage'),
        icon: 'trash',
        destructive: true,
        onPick: () => onDelete(message.id),
      })
    }
    return reactionItems
  }, [
    message._uploading,
    message.id,
    isMine,
    onReaction,
    onDelete,
    t,
  ])

  useEffect(() => {
    const sharedTrackId = message.shared_track_id
    if (!sharedTrackId) {
      setSharedTrack(null)
      setSharedTrackLoading(false)
      return
    }
    const cached = SHARED_TRACK_CACHE.get(sharedTrackId)
    if (cached) {
      setSharedTrack(cached)
      return
    }
    let cancelled = false
    setSharedTrackLoading(true)
    api.getTrack(sharedTrackId)
      .then((track) => {
        if (cancelled) return
        SHARED_TRACK_CACHE.set(sharedTrackId, track)
        setSharedTrack(track)
      })
      .catch(() => {
        if (cancelled) return
        setSharedTrack(null)
      })
      .finally(() => {
        if (!cancelled) {
          setSharedTrackLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [message.shared_track_id])

  useEffect(() => {
    const sharedAlbumId = message.shared_album_id
    if (!sharedAlbumId) {
      setSharedAlbum(null)
      setSharedAlbumLoading(false)
      return
    }
    const cached = SHARED_ALBUM_CACHE.get(sharedAlbumId)
    if (cached) {
      setSharedAlbum(cached)
      return
    }
    let cancelled = false
    setSharedAlbumLoading(true)
    api.getAlbum(sharedAlbumId)
      .then((album) => {
        if (cancelled) return
        SHARED_ALBUM_CACHE.set(sharedAlbumId, album)
        setSharedAlbum(album)
      })
      .catch(() => {
        if (cancelled) return
        setSharedAlbum(null)
      })
      .finally(() => {
        if (!cancelled) {
          setSharedAlbumLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [message.shared_album_id])

  useEffect(() => {
    const sharedPlaylistId = message.shared_playlist_id
    if (!sharedPlaylistId) {
      setSharedPlaylist(null)
      setSharedPlaylistLoading(false)
      return
    }
    const cached = SHARED_PLAYLIST_CACHE.get(sharedPlaylistId)
    if (cached) {
      setSharedPlaylist(cached)
      return
    }
    let cancelled = false
    setSharedPlaylistLoading(true)
    api.getPlaylist(sharedPlaylistId)
      .then((playlist) => {
        if (cancelled) return
        SHARED_PLAYLIST_CACHE.set(sharedPlaylistId, playlist)
        setSharedPlaylist(playlist)
      })
      .catch(() => {
        if (cancelled) return
        setSharedPlaylist(null)
      })
      .finally(() => {
        if (!cancelled) {
          setSharedPlaylistLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [message.shared_playlist_id])

  if (isSystem) {
    return (
      <div className="chat-msg system">
        <div className="chat-msg-system-card">
          <span className="chat-msg-system-icon">
            <Icon name="shield" size={16} />
          </span>
          <div className="chat-msg-system-body">
            <span className="chat-msg-system-label">
              {t('redesign.chats.systemLabel', {
                brand: brandLabel,
              })}
            </span>
            {message.content}
          </div>
        </div>
      </div>
    )
  }

  return (
    <m.div
      className={`chat-bubble-wrap re-bubble-wrap ${isMine ? 'mine' : 'theirs'}`}
      initial={
        reduce
          ? { opacity: 0 }
          : isMine
            ? { opacity: 0, scale: 0.6 }
            : { opacity: 0, y: 8 }
      }
      animate={
        reduce
          ? { opacity: 1 }
          : { opacity: 1, scale: 1, y: 0 }
      }
      transition={
        reduce ? { duration: 0 } : isMine ? SPRING_BOUNCY : SPRING_GENTLE
      }
    >
      <LongPressMenu
        items={menuItems}
        disabled={menuItems.length === 0}
      >
        <div
          className={`chat-bubble re-bubble ${isMine ? 'mine' : 'theirs'} ${message._uploading ? 'uploading' : ''}`}
        >
          {message.reply_to_id && (
          <div className="bubble-reply">
            {t('redesign.chats.replyTo', {
              id: message.reply_to_id,
            })}
          </div>
        )}

        {photoAtt && (
          <div
            className="bubble-photo"
            onClick={(e) => {
              e.stopPropagation()
              handlePhotoClick()
            }}
          >
            {!imgLoaded && !isLocal && (
              <div className="bubble-photo-placeholder shimmer" />
            )}
            <img
              src={photoSrc}
              alt=""
              className={`bubble-photo-img ${imgLoaded ? 'loaded' : ''}`}
              loading="lazy"
              onLoad={() => setImgLoaded(true)}
            />
            {message._uploading && (
              <div className="bubble-photo-upload">
                <div className="upload-spinner" />
                {onCancelUpload && (
                  <button
                    className="upload-cancel-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      onCancelUpload()
                    }}
                  >
                    <Icon name="x" size={16} />
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {voiceAtt && (
          <VoicePlayer
            fileKey={voiceAtt.file_key}
            duration={
              voiceAtt.duration_seconds ?? 0
            }
            waveform={voiceAtt.waveform ?? []}
          />
        )}

        {message.shared_track_id && (
          <div className="bubble-track-share slide-in">
            {sharedTrack ? (
              <div className="bubble-track-share-card">
                <div className="bubble-track-cover-wrap">
                  {sharedTrack.cover_key ? (
                    <img
                      src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(sharedTrack.cover_key)}`}
                      alt=""
                      className="bubble-track-cover"
                      loading="lazy"
                    />
                  ) : (
                    <span className="bubble-track-cover-placeholder">
                      <Icon name="music" size={18} />
                    </span>
                  )}
                </div>
                <div className="bubble-track-main">
                  <span className="bubble-track-label">
                    {t('redesign.chats.entityTrack')}
                  </span>
                  <span className="bubble-track-title">
                    {sharedTrack.title}
                  </span>
                  <span
                    className={
                      desktopFineNav &&
                      sharedTrack.artist
                        ? 'bubble-track-artist bubble-track-artist--nav'
                        : 'bubble-track-artist'
                    }
                    role={
                      desktopFineNav &&
                      sharedTrack.artist
                        ? 'link'
                        : undefined
                    }
                    tabIndex={
                      desktopFineNav &&
                      sharedTrack.artist
                        ? 0
                        : undefined
                    }
                    onClick={
                      desktopFineNav &&
                      sharedTrack.artist
                        ? (e) => {
                            e.stopPropagation()
                            void goArtistByName(
                              sharedTrack.artist,
                            )
                          }
                        : undefined
                    }
                    onKeyDown={
                      desktopFineNav &&
                      sharedTrack.artist
                        ? (e) => {
                            if (
                              e.key === 'Enter' ||
                              e.key === ' '
                            ) {
                              e.preventDefault()
                              e.stopPropagation()
                              void goArtistByName(
                                sharedTrack.artist,
                              )
                            }
                          }
                        : undefined
                    }
                  >
                    {sharedTrack.artist ||
                      t('trackCard.unknownArtist')}
                  </span>
                </div>
                <MotionPress
                  type="button"
                  variant="ghost"
                  className="bubble-track-play"
                  onClick={(e) => {
                    e.stopPropagation()
                    void playTrack(sharedTrack)
                  }}
                >
                  <Icon name="play" size={14} />
                  {t('redesign.chats.play')}
                </MotionPress>
              </div>
            ) : (
              <div className="bubble-track-share-fallback">
                {sharedTrackLoading
                  ? t('redesign.chats.loadingTrack')
                  : t('redesign.chats.trackNumber', {
                      id: message.shared_track_id,
                    })}
              </div>
            )}
          </div>
        )}

        {message.shared_album_id && (
          <div className="bubble-track-share slide-in">
            {sharedAlbum ? (
              <div className="bubble-track-share-card">
                <div className="bubble-track-cover-wrap">
                  {sharedAlbum.cover_key ? (
                    <img
                      src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(sharedAlbum.cover_key)}`}
                      alt=""
                      className="bubble-track-cover"
                      loading="lazy"
                    />
                  ) : (
                    <span className="bubble-track-cover-placeholder">
                      <Icon name="list" size={18} />
                    </span>
                  )}
                </div>
                <div className="bubble-track-main">
                  <span className="bubble-track-label">
                    {t('redesign.chats.entityAlbum')}
                  </span>
                  <span className="bubble-track-title">
                    {sharedAlbum.title}
                  </span>
                  <span className="bubble-track-artist">
                    {t('redesign.chats.tracksCount', {
                      count: sharedAlbum.tracks.length,
                    })}
                  </span>
                </div>
                <MotionPress
                  type="button"
                  variant="ghost"
                  className="bubble-track-play"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (sharedAlbum.tracks[0]) {
                      void playTrack(sharedAlbum.tracks[0])
                    }
                  }}
                >
                  <Icon name="play" size={14} />
                  {t('redesign.chats.play')}
                </MotionPress>
              </div>
            ) : (
              <div className="bubble-track-share-fallback">
                {sharedAlbumLoading
                  ? t('redesign.chats.loadingAlbum')
                  : t('redesign.chats.albumNumber', {
                      id: message.shared_album_id,
                    })}
              </div>
            )}
          </div>
        )}

        {message.shared_playlist_id && (
          <div className="bubble-track-share slide-in">
            {sharedPlaylist ? (
              <div className="bubble-track-share-card">
                <div className="bubble-track-cover-wrap">
                  <span className="bubble-track-cover-placeholder">
                    <Icon name="list" size={18} />
                  </span>
                </div>
                <div className="bubble-track-main">
                  <span className="bubble-track-label">
                    {t('redesign.chats.entityPlaylist')}
                  </span>
                  <span className="bubble-track-title">
                    {sharedPlaylist.name}
                  </span>
                  <span className="bubble-track-artist">
                    {t('redesign.chats.tracksCount', {
                      count: sharedPlaylist.tracks.length,
                    })}
                  </span>
                </div>
                <MotionPress
                  type="button"
                  variant="ghost"
                  className="bubble-track-play"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (sharedPlaylist.tracks[0]) {
                      void playTrack(sharedPlaylist.tracks[0])
                    }
                  }}
                >
                  <Icon name="play" size={14} />
                  {t('redesign.chats.play')}
                </MotionPress>
              </div>
            ) : (
              <div className="bubble-track-share-fallback">
                {sharedPlaylistLoading
                  ? t('redesign.chats.loadingPlaylist')
                  : t('redesign.chats.playlistNumber', {
                      id: message.shared_playlist_id,
                    })}
              </div>
            )}
          </div>
        )}

        {message.content && (
          <div className="bubble-text" dir="auto">
            {message.content}
          </div>
        )}

        <div className="bubble-meta">
          {message._uploading ? (
            <span className="bubble-time uploading-text">
              {t('redesign.chats.uploading')}
            </span>
          ) : (
            <span className="bubble-time">
              {new Date(
                message.created_at,
              ).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}
          {message.reactions?.length > 0 && (
            <div className="bubble-reactions">
              {message.reactions.map((r, i) => (
                <span
                  key={i}
                  className="bubble-reaction bounce-in"
                >
                  <MorphIcon
                    name={r.reaction_type}
                    size={14}
                  />
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      </LongPressMenu>
    </m.div>
  )
}
