import { useEffect, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { VoicePlayer } from '@/components/Chat/VoicePlayer'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
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

const REACTIONS = [
  'thumbs-up',
  'heart',
  'music',
  'sparkle',
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
  const [showBar, setShowBar] = useState(false)
  const [showReactions, setShowReactions] =
    useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)
  const [sharedTrack, setSharedTrack] = useState<Track | null>(null)
  const [sharedTrackLoading, setSharedTrackLoading] = useState(false)
  const [sharedAlbum, setSharedAlbum] =
    useState<AlbumWithTracksRecord | null>(null)
  const [sharedAlbumLoading, setSharedAlbumLoading] =
    useState(false)
  const [sharedPlaylist, setSharedPlaylist] =
    useState<PlaylistWithTracks | null>(null)
  const [sharedPlaylistLoading, setSharedPlaylistLoading] =
    useState(false)
  const { playTrack } = usePlayerActions()

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

  const handleTap = () => {
    if (message._uploading) return
    setShowBar((p) => !p)
  }

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
              Команда .sound
            </span>
            {message.content}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`chat-bubble-wrap ${isMine ? 'mine' : 'theirs'}`}
    >
      <div
        className={`chat-bubble ${isMine ? 'mine' : 'theirs'} msg-appear ${message._uploading ? 'uploading' : ''}`}
        onClick={handleTap}
      >
        {message.reply_to_id && (
          <div className="bubble-reply">
            Reply to #{message.reply_to_id}
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
                    Трек
                  </span>
                  <span className="bubble-track-title">
                    {sharedTrack.title}
                  </span>
                  <span className="bubble-track-artist">
                    {sharedTrack.artist || 'Неизвестный артист'}
                  </span>
                </div>
                <button
                  type="button"
                  className="bubble-track-play"
                  onClick={(e) => {
                    e.stopPropagation()
                    void playTrack(sharedTrack)
                  }}
                >
                  <Icon name="play" size={14} />
                  Play
                </button>
              </div>
            ) : (
              <div className="bubble-track-share-fallback">
                {sharedTrackLoading
                  ? 'Загрузка трека…'
                  : `Трек #${message.shared_track_id}`}
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
                  <span className="bubble-track-label">Альбом</span>
                  <span className="bubble-track-title">
                    {sharedAlbum.title}
                  </span>
                  <span className="bubble-track-artist">
                    {sharedAlbum.tracks.length} треков
                  </span>
                </div>
                <button
                  type="button"
                  className="bubble-track-play"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (sharedAlbum.tracks[0]) {
                      void playTrack(sharedAlbum.tracks[0])
                    }
                  }}
                >
                  <Icon name="play" size={14} />
                  Play
                </button>
              </div>
            ) : (
              <div className="bubble-track-share-fallback">
                {sharedAlbumLoading
                  ? 'Загрузка альбома…'
                  : `Альбом #${message.shared_album_id}`}
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
                  <span className="bubble-track-label">Плейлист</span>
                  <span className="bubble-track-title">
                    {sharedPlaylist.name}
                  </span>
                  <span className="bubble-track-artist">
                    {sharedPlaylist.tracks.length} треков
                  </span>
                </div>
                <button
                  type="button"
                  className="bubble-track-play"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (sharedPlaylist.tracks[0]) {
                      void playTrack(sharedPlaylist.tracks[0])
                    }
                  }}
                >
                  <Icon name="play" size={14} />
                  Play
                </button>
              </div>
            ) : (
              <div className="bubble-track-share-fallback">
                {sharedPlaylistLoading
                  ? 'Загрузка плейлиста…'
                  : `Плейлист #${message.shared_playlist_id}`}
              </div>
            )}
          </div>
        )}

        {message.content && (
          <div className="bubble-text">
            {message.content}
          </div>
        )}

        <div className="bubble-meta">
          {message._uploading ? (
            <span className="bubble-time uploading-text">
              отправка...
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
                  <Icon
                    name={r.reaction_type}
                    size={14}
                  />
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {showBar && !message._uploading && (
        <div
          className={`bubble-action-bar ${isMine ? 'mine' : 'theirs'} scale-in`}
        >
          <button
            className="bubble-action-btn"
            onClick={() => {
              setShowReactions((p) => !p)
              setShowBar(false)
            }}
          >
            <Icon name="sparkle" size={16} />
          </button>
          <button
            className="bubble-action-btn"
            onClick={() => {
              onDelete(message.id)
              setShowBar(false)
            }}
          >
            <Icon name="trash" size={16} />
          </button>
        </div>
      )}

      {showReactions && (
        <div
          className="reaction-picker-overlay"
          onClick={() => setShowReactions(false)}
        >
          <div
            className="reaction-picker scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            {REACTIONS.map((r) => (
              <button
                key={r}
                className="reaction-btn"
                onClick={() => {
                  onReaction(message.id, r)
                  setShowReactions(false)
                }}
              >
                <Icon name={r} size={24} />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
