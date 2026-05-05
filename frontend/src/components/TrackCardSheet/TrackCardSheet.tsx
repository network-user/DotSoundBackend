import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import {
  getInternalUserId,
  getIsAdmin,
} from '@/lib/telegram'
import { useLikes } from '@/store/LikesContext'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { TrackInfoContent } from '@/components/TrackInfoContent/TrackInfoContent'
import { Waveform } from '@/components/Waveform/Waveform'
import { WaveformBar } from '@/components/Waveform/WaveformBar'
import { useExitTransition } from '@/hooks/useExitTransition'
import { useToast } from '@/components/ui/Toast'
import {
  downloadTrack,
  isCached,
  removeTrack,
} from '@/lib/offlineCache'
import {
  clearThirdPartyStreamOverride,
  getThirdPartyStreamOverride,
  setThirdPartyStreamOverride,
} from '@/lib/streamDebugOverride'
import { hapticNotification } from '@/lib/telegram'
import type {
  AlbumWithTracksRecord,
  ChatListItem,
  Track,
  TrackCardResponse,
  TrackInfoResponse,
  TrackPlaybackVariantBrief,
} from '@/types/api'
import { CommentSection } from '@/components/Comments/CommentSection'
import { LyricsPanel } from './LyricsPanel'

const SPEED_OPTIONS = [0.75, 1, 1.25, 1.5]

function hasPipSupport(): boolean {
  try {
    return (
      typeof document !== 'undefined' &&
      'pictureInPictureEnabled' in document &&
      Boolean(
        (document as Document & {
          pictureInPictureEnabled?: boolean
        }).pictureInPictureEnabled,
      )
    )
  } catch {
    return false
  }
}

interface Props {
  onOpenAuthor: (authorId: number) => void
  onOpenArtist?: (name: string) => void
}

type ShareEntityType =
  | 'track'
  | 'album'
  | 'playlist'

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
    currentTime,
    duration,
    isPlaying,
  } = usePlayerState()
  const {
    track,
    isCardOpen,
    volume,
    playbackRate,
    abLoop,
  } = usePlayerMeta()
  const {
    closeCard,
    setVolume,
    togglePlay,
    seek,
    playNext,
    playPrev,
    openLyrics,
    openComplaint,
    openQueue,
    updateTrack,
    playTrack,
    skipForward,
    skipBackward,
    setPlaybackRate,
    setAbA,
    setAbB,
    clearAbLoop,
  } = usePlayerActions()
  const { t } = useTranslation()
  const toast = useToast()
  const videoRef = useRef<HTMLVideoElement>(null)
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
  const [trackInfo, setTrackInfo] =
    useState<TrackInfoResponse | null>(null)
  const [trackInfoRefreshing, setTrackInfoRefreshing] =
    useState(false)
  const trackInfoPollRef = useRef<
    ReturnType<typeof setTimeout> | null
  >(null)
  const isAdmin = getIsAdmin()

  const [coverKey, setCoverKey] = useState<
    string | null
  >(null)
  const [coverVer, setCoverVer] = useState(0)
  const [coverBusy, setCoverBusy] = useState(false)
  const [coverFailed, setCoverFailed] =
    useState(false)
  const [genCooldown, setGenCooldown] = useState(0)
  const [shareOpen, setShareOpen] = useState(false)
  const [shareChats, setShareChats] = useState<ChatListItem[]>([])
  const [shareLoading, setShareLoading] = useState(false)
  const [shareSendingConvId, setShareSendingConvId] = useState<number | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [sharePayload, setSharePayload] = useState<{
    id: number
    type: ShareEntityType
    title: string
  } | null>(null)
  const [albumEditOpen, setAlbumEditOpen] = useState(false)
  const [albumEditData, setAlbumEditData] =
    useState<AlbumWithTracksRecord | null>(null)
  const [albumEditBusy, setAlbumEditBusy] = useState(false)
  const [albumEditTitle, setAlbumEditTitle] = useState('')
  const [albumEditDesc, setAlbumEditDesc] = useState('')
  const [albumEditPublic, setAlbumEditPublic] = useState(false)
  const [albumAddTrackId, setAlbumAddTrackId] = useState<number | null>(null)
  const [albumTrackPool, setAlbumTrackPool] = useState<Track[]>([])
  const [relatedAlbumInfo, setRelatedAlbumInfo] = useState<{
    id: number
    title: string
  } | null>(null)
  const [albumTrackTitleDrafts, setAlbumTrackTitleDrafts] = useState<
    Record<number, string>
  >({})
  const [videoReady, setVideoReady] =
    useState(false)
  const videoEnabled =
    localStorage.getItem('setting-video-enabled') !== 'false'

  const sheetRef = useRef<HTMLDivElement>(null)
  const coverInputRef =
    useRef<HTMLInputElement>(null)
  const videoInputRef =
    useRef<HTMLInputElement>(null)
  const extrasWrapRef = useRef<HTMLDivElement>(null)
  const [extrasOpen, setExtrasOpen] = useState(false)
  const [streamOverrideDraft, setStreamOverrideDraft] =
    useState('')
  const streamDebugVisible =
    (import.meta.env.DEV || isAdmin) &&
    track != null &&
    track.access_mode === 'third_party_stream'

  useEffect(() => {
    if (
      !isCardOpen ||
      !track ||
      track.access_mode !== 'third_party_stream'
    ) {
      return
    }
    setStreamOverrideDraft(
      getThirdPartyStreamOverride(track.id) ?? '',
    )
  }, [isCardOpen, track?.id, track?.access_mode])

  useEffect(() => {
    if (!isCardOpen || !track) {
      setExtrasOpen(false)
      setCard(null)
      setShowLyrics(false)
      setEditingLyrics(false)
      setShowEdit(false)
      setAuthorAvatarUrl(null)
      setCoverKey(null)
      setCoverBusy(false)
      setVideoReady(false)
      setTrackInfo(null)
      setTrackInfoRefreshing(false)
      if (trackInfoPollRef.current) {
        clearTimeout(trackInfoPollRef.current)
        trackInfoPollRef.current = null
      }
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

    setTrackInfo(null)
    let cancelled = false
    let attempts = 0
    const pollInfo = async () => {
      try {
        const data = await api.getTrackInfo(track.id)
        if (cancelled) return
        setTrackInfo(data)
        if (
          (data.status === 'fetching' || data.status === 'pending') &&
          attempts < 30
        ) {
          attempts += 1
          trackInfoPollRef.current = setTimeout(pollInfo, 3000)
        }
      } catch {
        // silent вЂ” info block hidden if not loadable
      }
    }
    pollInfo()

    return () => {
      cancelled = true
      if (trackInfoPollRef.current) {
        clearTimeout(trackInfoPollRef.current)
        trackInfoPollRef.current = null
      }
    }
  }, [isCardOpen, track?.id])

  useEffect(() => {
    const albumFromCard = card?.album
    if (albumFromCard) {
      setRelatedAlbumInfo({
        id: albumFromCard.id,
        title: albumFromCard.title,
      })
      return
    }
    if (!track?.album_id) {
      setRelatedAlbumInfo(null)
      return
    }
    let cancelled = false
    api.getAlbum(track.album_id).then((album) => {
      if (!cancelled) {
        setRelatedAlbumInfo({
          id: album.id,
          title: album.title,
        })
      }
    }).catch(() => {
      if (!cancelled) {
        setRelatedAlbumInfo(null)
      }
    })
    return () => {
      cancelled = true
    }
  }, [card?.album?.id, card?.album?.title, track?.album_id])

  useEffect(() => {
    if (!extrasOpen) return
    const onDoc = (e: globalThis.PointerEvent) => {
      const el = extrasWrapRef.current
      if (el && !el.contains(e.target as Node)) {
        setExtrasOpen(false)
      }
    }
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') setExtrasOpen(false)
    }
    document.addEventListener('pointerdown', onDoc)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDoc)
      window.removeEventListener('keydown', onKey)
    }
  }, [extrasOpen])

  const handleRefreshTrackInfo = useCallback(async () => {
    if (!track || trackInfoRefreshing) return
    setTrackInfoRefreshing(true)
    try {
      const data = await api.refreshTrackInfo(track.id)
      setTrackInfo(data)
      if (data.status === 'fetching' || data.status === 'pending') {
        let attempts = 0
        const poll = async () => {
          try {
            const upd = await api.getTrackInfo(track.id)
            setTrackInfo(upd)
            if (
              (upd.status === 'fetching' || upd.status === 'pending') &&
              attempts < 30
            ) {
              attempts += 1
              trackInfoPollRef.current = setTimeout(poll, 3000)
            }
          } catch {}
        }
        poll()
      }
    } catch {
      // noop
    } finally {
      setTrackInfoRefreshing(false)
    }
  }, [track, trackInfoRefreshing])

  useEffect(() => {
    if (genCooldown <= 0) return
    const t = setInterval(
      () =>
        setGenCooldown((v) => Math.max(0, v - 1)),
      1000,
    )
    return () => clearInterval(t)
  }, [genCooldown])

  const goToArtist = useCallback(
    (name: string) => {
      if (!onOpenArtist) return
      closeCard()
      requestAnimationFrame(() => onOpenArtist(name))
    },
    [closeCard, onOpenArtist],
  )

  const goToAuthor = useCallback(
    (authorId: number) => {
      closeCard()
      requestAnimationFrame(() => onOpenAuthor(authorId))
    },
    [closeCard, onOpenAuthor],
  )

  const handleBackdrop = (
    e: React.MouseEvent,
  ) => {
    if (e.target === e.currentTarget) closeCard()
  }

  const formatShareChatTitle = useCallback((item: ChatListItem): string => {
    if (item.conversation.type === 'saved') {
      return 'РР·Р±СЂР°РЅРЅРѕРµ'
    }
    if (item.conversation.title?.trim()) {
      return item.conversation.title.trim()
    }
    const peer = item.peer
    const name = peer?.display_name
      || [peer?.first_name, peer?.last_name]
        .filter(Boolean)
        .join(' ')
    if (name && name.trim()) {
      return name.trim()
    }
    if (peer?.username) {
      return `@${peer.username}`
    }
    return `Р§Р°С‚ #${item.conversation.id}`
  }, [])

  const openShareModal = useCallback(async (payload: {
    id: number
    type: ShareEntityType
    title: string
  }) => {
    setSharePayload(payload)
    setShareOpen(true)
    setShareLoading(true)
    setShareError(null)
    try {
      const chats = await api.listChats()
      setShareChats(chats)
    } catch {
      setShareError('РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ С‡Р°С‚С‹')
    } finally {
      setShareLoading(false)
    }
  }, [])

  const handleShareToChat = useCallback(async (conversationId: number) => {
    if (!sharePayload) return
    setShareSendingConvId(conversationId)
    setShareError(null)
    const msgTypeMap: Record<ShareEntityType, string> = {
      track: 'track_share',
      album: 'album_share',
      playlist: 'playlist_share',
    }
    const opts: {
      type: string
      shared_track_id?: number
      shared_album_id?: number
      shared_playlist_id?: number
    } = {
      type: msgTypeMap[sharePayload.type],
    }
    if (sharePayload.type === 'track') {
      opts.shared_track_id = sharePayload.id
    } else if (sharePayload.type === 'album') {
      opts.shared_album_id = sharePayload.id
    } else {
      opts.shared_playlist_id = sharePayload.id
    }
    try {
      await api.sendMessage(conversationId, '', opts)
      setShareOpen(false)
      toast.success('РўСЂРµРє РѕС‚РїСЂР°РІР»РµРЅ')
    } catch {
      setShareError('РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ С‚СЂРµРє')
    } finally {
      setShareSendingConvId(null)
    }
  }, [sharePayload, toast])

  const openAlbumEditor = useCallback(async () => {
    const internalId = getInternalUserId()
    const canOwnerEdit = Boolean(
      internalId !== null &&
      track?.uploaded_by_id === internalId,
    )
    if (!relatedAlbumInfo || (!isAdmin && !canOwnerEdit)) return
    setAlbumEditBusy(true)
    try {
      const [album, myLib] = await Promise.all([
        api.getAlbum(relatedAlbumInfo.id),
        api.getMyLibrary(1, 100, false),
      ])
      setAlbumEditData(album)
      setAlbumEditTitle(album.title)
      setAlbumEditDesc(album.description || '')
      setAlbumEditPublic(album.is_public)
      setAlbumTrackPool(myLib.items)
      setAlbumTrackTitleDrafts(
        Object.fromEntries(
          album.tracks.map((t) => [t.id, t.title || '']),
        ),
      )
      setAlbumEditOpen(true)
    } catch {
      toast.error('РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РєСЂС‹С‚СЊ СЂРµРґР°РєС‚РѕСЂ Р°Р»СЊР±РѕРјР°')
    } finally {
      setAlbumEditBusy(false)
    }
  }, [relatedAlbumInfo?.id, isAdmin, track?.uploaded_by_id, toast])

  const refreshAlbumEditor = useCallback(async () => {
    if (!albumEditData) return
    const album = await api.getAlbum(albumEditData.id)
    setAlbumEditData(album)
    setAlbumEditTitle(album.title)
    setAlbumEditDesc(album.description || '')
    setAlbumEditPublic(album.is_public)
    setAlbumTrackTitleDrafts(
      Object.fromEntries(
        album.tracks.map((t) => [t.id, t.title || '']),
      ),
    )
  }, [albumEditData?.id])

  const saveAlbumMeta = useCallback(async () => {
    if (!albumEditData || !isAdmin) return
    setAlbumEditBusy(true)
    try {
      await api.updateAlbum(albumEditData.id, {
        title: albumEditTitle.trim() || albumEditData.title,
        description: albumEditDesc.trim() || null,
        is_public: albumEditPublic,
      })
      await refreshAlbumEditor()
    } finally {
      setAlbumEditBusy(false)
    }
  }, [
    albumEditData?.id,
    albumEditTitle,
    albumEditDesc,
    albumEditPublic,
    isAdmin,
    refreshAlbumEditor,
  ])

  const removeAlbumTrack = useCallback(async (trackId: number) => {
    if (!albumEditData || !isAdmin) return
    await api.removeTrackFromAlbum(albumEditData.id, trackId)
    await refreshAlbumEditor()
  }, [albumEditData?.id, isAdmin, refreshAlbumEditor])

  const addAlbumTrack = useCallback(async () => {
    if (!albumEditData || !isAdmin || !albumAddTrackId) return
    await api.addTrackToAlbum(albumEditData.id, albumAddTrackId)
    setAlbumAddTrackId(null)
    await refreshAlbumEditor()
  }, [albumEditData?.id, isAdmin, albumAddTrackId, refreshAlbumEditor])

  const moveAlbumTrack = useCallback(async (index: number, dir: -1 | 1) => {
    if (!albumEditData || !isAdmin) return
    const nextIndex = index + dir
    if (nextIndex < 0 || nextIndex >= albumEditData.tracks.length) return
    const ids = albumEditData.tracks.map((t) => t.id)
    const tmp = ids[index]
    ids[index] = ids[nextIndex]
    ids[nextIndex] = tmp
    await api.setAlbumTrackOrder(albumEditData.id, ids)
    await refreshAlbumEditor()
  }, [albumEditData?.id, albumEditData?.tracks, isAdmin, refreshAlbumEditor])

  const saveAlbumTrackTitle = useCallback(async (trackId: number) => {
    if (!isAdmin) return
    const raw = albumTrackTitleDrafts[trackId]
    const title = raw?.trim()
    if (!title) return
    await api.updateTrack(trackId, { title })
    await refreshAlbumEditor()
  }, [isAdmin, albumTrackTitleDrafts, refreshAlbumEditor])

  const handleAuthor = () => {
    if (track?.artist && onOpenArtist) {
      goToArtist(track.artist)
      return
    }
    if (card?.author?.id) {
      goToAuthor(card.author.id)
    }
  }

  const handleUploader = () => {
    if (card?.author?.id) {
      goToAuthor(card.author.id)
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

  const exit = useExitTransition(
    Boolean(isCardOpen && track),
  )

  const [downloadState, setDownloadState] = useState<
    'idle' | 'downloading' | 'cached'
  >('idle')
  const [downloadPct, setDownloadPct] = useState(0)

  useEffect(() => {
    if (!track) return
    isCached(track.id).then((c) =>
      setDownloadState(c ? 'cached' : 'idle'),
    )
  }, [track?.id])

  const handleDownload = async () => {
    if (!track) return
    if (downloadState === 'cached') {
      await removeTrack(track.id)
      setDownloadState('idle')
      setDownloadPct(0)
      toast.info(t('trackSheet.removedFromDownloads'))
      return
    }
    setDownloadState('downloading')
    setDownloadPct(0)
    try {
      await downloadTrack(track, (loaded, total) => {
        if (total) {
          setDownloadPct(
            Math.round((loaded / total) * 100),
          )
        }
      })
      setDownloadState('cached')
      hapticNotification('success')
      toast.success(
        t('trackSheet.offlineReady'),
      )
    } catch (e) {
      setDownloadState('idle')
      const msg =
        e instanceof Error
          ? e.message
          : t('trackSheet.downloadError')
      toast.error(msg)
    }
  }

  const playbackVariants = useMemo((): TrackPlaybackVariantBrief[] => {
    if (!track) return []
    const fromTrack = track.playback_variants
    if (fromTrack && fromTrack.length > 0) return fromTrack
    return card?.playback_variants ?? []
  }, [track, card])

  if (!exit.mounted || !track) return null

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
      className={`tcs-backdrop${exit.cls}`}
      onClick={handleBackdrop}
    >
      <div
        className={`tcs-sheet${hasActiveVideo ? ' tcs-video-mode' : ''}${exit.cls}`}
        ref={sheetRef}
      >
        <div className="tcs-handle" />
        <button
          className="tcs-close"
          onClick={closeCard}
          aria-label={t('trackSheet.close')}
        >
          <Icon name="x" size={22} />
        </button>

        <div
          key={track.id}
          className="tcs-track-content"
        >
        {hasActiveVideo && (
          <>
            <video
              ref={videoRef}
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
            {hasPipSupport() && (
              <button
                type="button"
                className="tcs-pip-btn"
                onClick={async () => {
                  const v = videoRef.current
                  if (!v) return
                  try {
                    if (
                      document.pictureInPictureElement
                    ) {
                      await document.exitPictureInPicture()
                    } else {
                      await v.requestPictureInPicture()
                    }
                  } catch {
                    toast.warning(
                      t('trackSheet.pipUnavailable'),
                    )
                  }
                }}
                aria-label={t('trackSheet.pipAria')}
                title={t('trackSheet.pipTitle')}
              >
                <Icon name="pip" size={16} />
              </button>
            )}
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
          <div className="tcs-cover-wrap">
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
            <div className="tcs-cover-wave-area" aria-hidden>
              <div className="tcs-cover-wave-gradient" />
              <Waveform
                overlay
                height={64}
                bars={36}
                className="tcs-cover-waveform"
              />
            </div>
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
                catalogType={track.catalog_type}
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
                catalogType={track.catalog_type}
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
                    if (track.artist && onOpenArtist) {
                      goToArtist(track.artist)
                    }
                  }}
                  style={
                    track.artist
                      ? { cursor: 'pointer' }
                      : undefined
                  }
                >
                  {track.artist ?? 'вЂ”'}
                </p>
              </div>
              <button
                className="icon-btn"
                onClick={() => {
                  void openShareModal({
                    id: track.id,
                    type: 'track',
                    title: track.title || 'track',
                  })
                }}
              >
                <Icon name="share" size={18} />
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
                  onClick={() => {
                    void openShareModal({
                      id: track.id,
                      type: 'track',
                      title: track.title || 'track',
                    })
                  }}
                >
                  <Icon
                    name="share"
                    size={18}
                  />
                </button>
              </div>
              <p
                className="tcs-artist"
                onClick={() => {
                  if (track.artist && onOpenArtist) {
                    goToArtist(track.artist)
                  }
                }}
                style={
                  track.artist
                    ? { cursor: 'pointer' }
                    : undefined
                }
              >
                {track.artist ?? 'вЂ”'}
              </p>
            </>
          )}
          <p className="tcs-meta">
            {track.catalog_type === 'ugc' &&
              t('trackSheet.catUgc')}
            {track.catalog_type === 'licensed' &&
              t('trackSheet.catLicensed')}
            {track.catalog_type ===
              'external_reference' &&
              t('trackSheet.catRef')}
          </p>
          {relatedAlbumInfo && (
            <div className="tcs-share-related-row">
              <span className="tcs-share-related-title">
                Альбом: {relatedAlbumInfo.title}
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="tcs-share-related-btn"
                  onClick={() => {
                    void openShareModal({
                      id: relatedAlbumInfo.id,
                      type: 'album',
                      title: relatedAlbumInfo.title,
                    })
                  }}
                >
                  <Icon name="share" size={14} />
                  Поделиться
                </button>
                {(isAdmin || isOwner) && (
                  <button
                    type="button"
                    className="tcs-share-related-btn"
                    onClick={() => {
                      void openAlbumEditor()
                    }}
                    disabled={albumEditBusy}
                  >
                    <Icon name="edit" size={14} />
                    Редактировать
                  </button>
                )}
              </div>
            </div>
          )}
          {card?.author && (
            <div
              className="tcs-author-row"
              onClick={handleUploader}
              title={t('trackSheet.goUploader')}
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
                  t('trackSheet.uploader')}
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
            {track.waveform_data && track.waveform_data.length > 0 ? (
              <WaveformBar
                data={track.waveform_data}
                progress={pct}
                onSeek={seek}
                height={40}
                className="tcs-waveform-bar"
              />
            ) : (
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
              style={{ ['--progress' as string]: `${pct}%` }}
            />
            )}
            <div className="tcs-time">
              <span>{fmt(currentTime)}</span>
              <span>{fmt(duration)}</span>
            </div>
          </div>
          <div className="tcs-play-row">
            <button
              className="ctrl-btn"
              onClick={() => skipBackward(15)}
              aria-label={t('trackSheet.seekBack')}
              title={t('trackSheet.seekBackTitle')}
            >
              <Icon
                name="rewind-5"
                size={22}
              />
            </button>
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
              className={`play-btn${
                isPlaying ? ' play-btn--playing' : ''
              }`}
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
            <button
              className="ctrl-btn"
              onClick={() => skipForward(15)}
              aria-label={t('trackSheet.seekForward')}
              title={t('trackSheet.seekForwardTitle')}
            >
              <Icon
                name="forward-5"
                size={22}
              />
            </button>
          </div>
          <div
            className="tcs-extras-wrap"
            ref={extrasWrapRef}
          >
            <button
              type="button"
              className="tcs-extras-trigger"
              onClick={() =>
                setExtrasOpen((v) => !v)
              }
              aria-expanded={extrasOpen}
              aria-haspopup="true"
              aria-controls={
                extrasOpen ? 'tcs-extras-menu' : undefined
              }
              aria-label={t('trackSheet.moreMenu')}
            >
              <Icon name="settings" size={18} />
              {t('trackSheet.more')}
            </button>
            {extrasOpen && (
              <div
                className="tcs-extras-popover"
                id="tcs-extras-menu"
                role="menu"
              >
                <div className="pb-extras">
                  <button
                    type="button"
                    className="pb-extras-btn"
                    role="menuitem"
                    onClick={() => {
                      setExtrasOpen(false)
                      openQueue()
                    }}
                    aria-label={t('trackSheet.queue')}
                  >
                    <Icon
                      name="queue"
                      size={14}
                    />
                    {t('trackSheet.queue')}
                  </button>
                  {SPEED_OPTIONS.map((rate) => (
                    <button
                      type="button"
                      key={rate}
                      className={`pb-extras-btn${playbackRate === rate ? ' active' : ''}`}
                      role="menuitem"
                      onClick={() =>
                        setPlaybackRate(rate)
                      }
                      aria-pressed={
                        playbackRate === rate
                      }
                    >
                      {rate}Г—
                    </button>
                  ))}
                  <button
                    type="button"
                    className={`pb-extras-btn${abLoop.a !== null ? ' active' : ''}`}
                    role="menuitem"
                    onClick={() => setAbA()}
                    title={t('trackSheet.abA')}
                  >
                    <Icon name="loop" size={14} />A
                    {abLoop.a !== null
                      ? ` ${fmt(abLoop.a)}`
                      : ''}
                  </button>
                  <button
                    type="button"
                    className={`pb-extras-btn${abLoop.b !== null ? ' active' : ''}`}
                    role="menuitem"
                    onClick={() => setAbB()}
                    title={t('trackSheet.abB')}
                    disabled={abLoop.a === null}
                  >
                    <Icon name="loop" size={14} />B
                    {abLoop.b !== null
                      ? ` ${fmt(abLoop.b)}`
                      : ''}
                  </button>
                  {(abLoop.a !== null ||
                    abLoop.b !== null) && (
                    <button
                      type="button"
                      className="pb-extras-btn"
                      role="menuitem"
                      onClick={clearAbLoop}
                      title={t('trackSheet.abReset')}
                    >
                      Г—
                    </button>
                  )}
                </div>
              </div>
            )}
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
              {t('trackSheet.like')}
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
              {t('trackSheet.dislike')}
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
              {t('trackSheet.lyrics')}
            </span>
          </button>

          <button
            className={`tcs-action-btn${downloadState === 'cached' ? ' active' : ''}`}
            onClick={handleDownload}
            disabled={downloadState === 'downloading'}
          >
            <Icon
              name={
                downloadState === 'cached'
                  ? 'check'
                  : 'cloud-download'
              }
              size={20}
            />
            <span className="tcs-action-label">
              {downloadState === 'cached'
                ? t('trackSheet.downloaded')
                : downloadState === 'downloading'
                  ? `${downloadPct}%`
                  : t('trackSheet.download')}
            </span>
          </button>

          <button
            className="tcs-action-btn"
            onClick={handleAuthor}
            disabled={!track?.artist && !card?.author}
          >
            <Icon name="user" size={20} />
            <span className="tcs-action-label">
              {t('trackSheet.toAuthor')}
            </span>
          </button>

          {(isAdmin || (isOwner && track.catalog_type === 'ugc')) && (
            <button
              className={`tcs-action-btn${showEdit ? ' active' : ''}`}
              onClick={() =>
                setShowEdit((v) => !v)
              }
            >
              <Icon name="edit" size={20} />
              <span className="tcs-action-label">
                {t('trackSheet.edit')}
              </span>
            </button>
          )}


          <button
            className="tcs-action-btn"
            onClick={openComplaint}
          >
            <Icon name="flag" size={20} />
            <span className="tcs-action-label">
              {t('trackSheet.complaint')}
            </span>
          </button>
        </div>

        {showEdit && (isAdmin || (isOwner && track.catalog_type === 'ugc')) && (
          <div className="tcs-edit-panel">
            <div className="tcs-edit-title">
              {t('trackSheet.editing')}
            </div>
            <div className="tcs-edit-actions">
              {(isAdmin || track.catalog_type === 'ugc') && (
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
                    {t('trackSheet.cover')}
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
                      ? t('trackSheet.seconds', {
                        n: genCooldown,
                      })
                      : t('trackSheet.generate')}
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
                  {t('trackSheet.coverRestore')}
                </button>
              )}
              {(track.catalog_type !== 'external_reference' ||
                isAdmin) && (
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
                {t('trackSheet.lyricsNoun')}
              </button>
              )}
              <button
                className="tcs-edit-btn"
                onClick={handleVideoUpload}
              >
                <Icon
                  name="video"
                  size={18}
                />
                {t('trackSheet.video')}
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
                  {t('trackSheet.removeVideo')}
                </button>
              )}
            </div>
          </div>
        )}

        {editingLyrics &&
          (isOwner || isAdmin) && (
          <div className="tcs-lyrics-edit-inline">
            <LyricsPanel
              trackId={track.id}
              isOwner={isOwner}
              catalogType={track.catalog_type}
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
              {t('trackSheet.closeEditor')}
            </button>
          </div>
        )}

        {playbackVariants.length > 1 && (
          <div className="tcs-source-variants">
            <span className="tcs-source-label">
              {t('trackSheet.playbackSource', 'РСЃС‚РѕС‡РЅРёРє')}
            </span>
            <div className="tcs-variant-chips" role="tablist">
              {playbackVariants.map((v) => (
                <button
                  key={v.track_id}
                  type="button"
                  role="tab"
                  aria-selected={v.track_id === track.id}
                  className={`tcs-variant-chip${
                    v.track_id === track.id ? ' active' : ''
                  }`}
                  onClick={async () => {
                    if (v.track_id === track.id) return
                    try {
                      const full = await api.getTrack(v.track_id)
                      playTrack(full)
                    } catch {
                      toast.error(t('trackSheet.sourceSwitchError', 'РќРµ СѓРґР°Р»РѕСЃСЊ РїРµСЂРµРєР»СЋС‡РёС‚СЊ'))
                    }
                  }}
                >
                  {v.source_name ||
                    v.source_platform ||
                    v.source}
                </button>
              ))}
            </div>
          </div>
        )}

        {(track.source_url || track.sc_url) && (
          <div className="tcs-source-info">
            <span className="tcs-source-label">
              {t('trackSheet.source')}{' '}
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
                ? t('trackSheet.disclaimerStream')
                : t('trackSheet.disclaimerMeta')}
            </p>
          </div>
        )}

        {streamDebugVisible && (
          <details className="tcs-source-info tcs-stream-debug">
            <summary>
              {t('trackSheet.streamDebugTitle')}
            </summary>
            <div className="tcs-stream-debug-body">
              <input
                type="url"
                className="tcs-stream-debug-url-input"
                value={streamOverrideDraft}
                onChange={(e) =>
                  setStreamOverrideDraft(e.target.value)
                }
                placeholder={t(
                  'trackSheet.streamDebugPlaceholder',
                )}
                spellCheck={false}
                autoComplete="off"
              />
              <div className="tcs-stream-debug-actions">
                <button
                  type="button"
                  className="tcs-edit-btn"
                  onClick={() => {
                    const u =
                      streamOverrideDraft.trim()
                    if (
                      !/^https?:\/\//i.test(u)
                    ) {
                      toast.error(
                        t(
                          'trackSheet.streamDebugInvalid',
                        ),
                      )
                      return
                    }
                    setThirdPartyStreamOverride(
                      track.id,
                      u,
                    )
                    void playTrack(track)
                  }}
                >
                  {t('trackSheet.streamDebugApply')}
                </button>
                <button
                  type="button"
                  className="tcs-edit-btn"
                  onClick={() => {
                    clearThirdPartyStreamOverride(
                      track.id,
                    )
                    setStreamOverrideDraft('')
                    void playTrack(track)
                  }}
                >
                  {t('trackSheet.streamDebugClear')}
                </button>
              </div>
              <p className="tcs-stream-debug-hint">
                {t('trackSheet.streamDebugHint')}
              </p>
            </div>
          </details>
        )}

        {similarTracks.length > 0 && (
          <div className="tcs-similar-section">
            <h3 className="tcs-similar-title">
              {t('trackSheet.similar')}
            </h3>
            <div className="tcs-similar-list">
              {similarTracks.slice(0, 5).map((st) => (
                <div
                  key={st.id}
                  className="tcs-similar-item"
                  onClick={() => {
                    closeCard()
                    requestAnimationFrame(() =>
                      playTrack(st),
                    )
                  }}
                >
                  <CoverImage coverKey={st.cover_key} />
                  <div className="tcs-similar-info">
                    <span className="tcs-similar-track-title">{st.title}</span>
                    <span className="tcs-similar-track-artist">{st.artist ?? 'вЂ”'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {(trackInfo?.status === 'done' ||
          trackInfo?.status === 'fetching' ||
          trackInfo?.status === 'pending' ||
          isAdmin) && (
          <div className="tcs-info-section">
            <div className="tcs-info-section-header">
              <h3 className="tcs-info-section-title">
                {t('trackSheet.aboutTrack')}
              </h3>
            </div>
            {isAdmin && (
              <div className="tcs-info-debug-panel">
                <button
                  className="tcs-info-debug-btn"
                  onClick={handleRefreshTrackInfo}
                  disabled={trackInfoRefreshing}
                >
                  <Icon
                    name={trackInfoRefreshing ? 'settings' : 'refresh'}
                    size={14}
                    className={trackInfoRefreshing ? 'tcs-spin' : undefined}
                  />
                  {trackInfoRefreshing
                    ? t('trackSheet.debugLoading')
                    : t('trackSheet.debugBypass')}
                </button>
                <div className="tcs-info-debug-meta">
                  <span>
                    {t('trackSheet.status')}{' '}
                    <b>
                      {trackInfo?.status ?? 'вЂ”'}
                    </b>
                  </span>
                  {trackInfo?.fetched_at && (
                    <span>
                      {t('trackSheet.updated')}{' '}
                      {new Date(
                        trackInfo.fetched_at,
                      ).toLocaleString()}
                    </span>
                  )}
                  {trackInfo?.content && (
                    <span>
                      {t('trackSheet.chars')}{' '}
                      {trackInfo.content.length}
                    </span>
                  )}
                </div>
              </div>
            )}
            {(trackInfo?.status === 'fetching' ||
              trackInfo?.status === 'pending' ||
              trackInfoRefreshing) && (
              <p className="tcs-info-placeholder">
                {t('trackSheet.preparingInfo')}
              </p>
            )}
            {trackInfo?.status === 'done' && trackInfo.content && (
              <TrackInfoContent
                content={trackInfo.content}
                trackArtist={track.artist ?? null}
                onOpenArtist={(name) => {
                  if (onOpenArtist) goToArtist(name)
                }}
              />
            )}
            {trackInfo?.status === 'not_found' && (
              <p className="tcs-info-placeholder">
                {t('trackSheet.infoNotFound')}
              </p>
            )}
            {trackInfo?.status === 'failed' && (
              <p className="tcs-info-placeholder">
                {t('trackSheet.infoError')}
              </p>
            )}
          </div>
        )}

        {track.is_public && (
          <div className="tcs-comments-section">
            <CommentSection
              trackId={track.id}
              trackOwnerId={track.uploaded_by_id}
            />
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
        {albumEditOpen && albumEditData && (
          <div
            className="share-modal-overlay fade-in"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setAlbumEditOpen(false)
              }
            }}
          >
            <div className="share-modal scale-in">
              <div className="share-modal-header">
                <div className="share-modal-title-wrap">
                  <h3 className="share-modal-title">Редактирование альбома</h3>
                  <p className="share-modal-subtitle">{albumEditData.title}</p>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setAlbumEditOpen(false)}
                  aria-label="Закрыть"
                >
                  <Icon name="x" size={18} />
                </button>
              </div>
              <div className="form-group">
                <label className="form-label">Название</label>
                <input
                  className="form-input"
                  value={albumEditTitle}
                  onChange={(e) => setAlbumEditTitle(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Описание</label>
                <input
                  className="form-input"
                  value={albumEditDesc}
                  onChange={(e) => setAlbumEditDesc(e.target.value)}
                />
              </div>
              <label className="hint" style={{ display: 'block', marginBottom: 12 }}>
                <input
                  type="checkbox"
                  checked={albumEditPublic}
                  onChange={(e) => setAlbumEditPublic(e.target.checked)}
                  style={{ marginRight: 8 }}
                />
                Публичный
              </label>
              <button
                className="btn-primary"
                onClick={() => {
                  void saveAlbumMeta()
                }}
                disabled={albumEditBusy}
              >
                {albumEditBusy ? 'Сохранение...' : 'Сохранить'}
              </button>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <select
                  className="form-input"
                  value={albumAddTrackId ?? ''}
                  onChange={(e) => setAlbumAddTrackId(Number(e.target.value) || null)}
                >
                  <option value="">Добавить трек...</option>
                  {albumTrackPool
                    .filter((t) => !albumEditData.tracks.some((at) => at.id === t.id))
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.title} {t.artist ? `- ${t.artist}` : ''}
                      </option>
                    ))}
                </select>
                <button className="btn-secondary" onClick={() => void addAlbumTrack()}>
                  Добавить
                </button>
              </div>
              <div style={{ marginTop: 12 }}>
                {albumEditData.tracks.map((t, idx) => (
                  <div
                    key={t.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      marginBottom: 8,
                    }}
                  >
                    <input
                      className="form-input"
                      style={{ flex: 1 }}
                      value={albumTrackTitleDrafts[t.id] ?? t.title}
                      onChange={(e) => {
                        setAlbumTrackTitleDrafts((prev) => ({
                          ...prev,
                          [t.id]: e.target.value,
                        }))
                      }}
                    />
                    <button className="icon-btn" onClick={() => void saveAlbumTrackTitle(t.id)}>
                      <Icon name="check" size={14} />
                    </button>
                    <button className="icon-btn" onClick={() => void moveAlbumTrack(idx, -1)}>
                      ^
                    </button>
                    <button className="icon-btn" onClick={() => void moveAlbumTrack(idx, 1)}>
                      v
                    </button>
                    <button className="icon-btn" onClick={() => void removeAlbumTrack(t.id)}>
                      <Icon name="x" size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
        {shareOpen && (
          <div
            className="share-modal-overlay fade-in"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setShareOpen(false)
              }
            }}
          >
            <div className="share-modal scale-in">
              <div className="share-modal-header">
                <div className="share-modal-title-wrap">
                  <h3 className="share-modal-title">
                    {sharePayload?.type === 'album'
                      ? 'РџРѕРґРµР»РёС‚СЊСЃСЏ Р°Р»СЊР±РѕРјРѕРј'
                      : sharePayload?.type === 'playlist'
                        ? 'РџРѕРґРµР»РёС‚СЊСЃСЏ РїР»РµР№Р»РёСЃС‚РѕРј'
                        : 'РџРѕРґРµР»РёС‚СЊСЃСЏ С‚СЂРµРєРѕРј'}
                  </h3>
                  <p className="share-modal-subtitle">
                    {sharePayload?.title || 'Р’С‹Р±РµСЂРёС‚Рµ С‡Р°С‚ РґР»СЏ РѕС‚РїСЂР°РІРєРё'}
                  </p>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShareOpen(false)}
                  aria-label="Р—Р°РєСЂС‹С‚СЊ"
                >
                  <Icon name="x" size={18} />
                </button>
              </div>

              {shareLoading ? (
                <div className="share-modal-loading">
                  <div className="loader" />
                </div>
              ) : shareChats.length === 0 ? (
                <div className="share-modal-empty">
                  РќРµС‚ РґРѕСЃС‚СѓРїРЅС‹С… С‡Р°С‚РѕРІ
                </div>
              ) : (
                <div className="share-chat-list">
                  {shareChats.map((item) => {
                    const convId = item.conversation.id
                    const sending = shareSendingConvId === convId
                    return (
                      <button
                        key={convId}
                        type="button"
                        className="share-chat-row"
                        onClick={() => {
                          void handleShareToChat(convId)
                        }}
                        disabled={shareSendingConvId !== null}
                      >
                        <span className="share-chat-icon">
                          <Icon
                            name={
                              item.conversation.type === 'group'
                                ? 'users-following'
                                : item.conversation.type === 'saved'
                                  ? 'heart'
                                  : 'user'
                            }
                            size={16}
                          />
                        </span>
                        <span className="share-chat-meta">
                          <span className="share-chat-title">
                            {formatShareChatTitle(item)}
                          </span>
                        </span>
                        <span className="share-chat-action">
                          {sending ? 'РћС‚РїСЂР°РІРєР°вЂ¦' : 'РћС‚РїСЂР°РІРёС‚СЊ'}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}

              {shareError && (
                <div className="share-modal-error">
                  {shareError}
                </div>
              )}
            </div>
          </div>
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



