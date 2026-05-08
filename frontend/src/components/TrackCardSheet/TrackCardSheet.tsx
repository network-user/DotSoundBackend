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
  hapticTick,
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
import { showIsland } from '@/lib/island'
import { useSound } from '@/store/SoundContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import {
  clearThirdPartyStreamOverride,
  getThirdPartyStreamOverride,
  setThirdPartyStreamOverride,
} from '@/lib/streamDebugOverride'
import type {
  AlbumWithTracksRecord,
  ChatListItem,
  Track,
  TrackCardResponse,
  TrackInfoResponse,
  TrackPlaybackVariantBrief,
} from '@/types/api'
import { CommentSection } from '@/components/Comments/CommentSection'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { m, useReducedMotion } from '@/lib/motion'
import { type PanInfo } from 'framer-motion'
import { LyricsPanel } from './LyricsPanel'
import { buildTrackCardSummaryLine } from '@/lib/trackCardFormat'

const TCS_DRAG_CLOSE_THRESHOLD = 100

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

function fmtListenWhen(iso: string) {
  const d = new Date(iso)
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

function coverUrl(k: string, v: number) {
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(k)}&v=${v}`
}

export function TrackCardSheet({
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
    getPreciseTime,
    playNext,
    playPrev,
    openLyrics,
    openComplaint,
    openQueue,
    updateTrack,
    playTrack,
    startRadio,
    skipForward,
    skipBackward,
    setPlaybackRate,
    setAbA,
    setAbB,
    clearAbLoop,
    sleepMode,
    sleepRemainingSec,
    setSleepTimerMinutes,
    setSleepTimerEndOfTrack,
    cancelSleepTimer,
  } = usePlayerActions()
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const [isCoarsePointer, setIsCoarsePointer] = useState(false)
  const sound = useSound()
  const videoRef = useRef<HTMLVideoElement>(null)

  const handleSheetDragEnd = useCallback(
    (_: unknown, info: PanInfo) => {
      if (info.offset.y > TCS_DRAG_CLOSE_THRESHOLD) {
        closeCard()
      }
    },
    [closeCard],
  )
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
  const [showTrackInfo, setShowTrackInfo] =
    useState(false)
  const [editingLyrics, setEditingLyrics] =
    useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [similarTracks, setSimilarTracks] =
    useState<Track[]>([])
  usePrefetchTracks(similarTracks, 'similar_in_card')
  const [loading, setLoading] = useState(false)
  const [smoothCurrentTime, setSmoothCurrentTime] = useState(0)
  const [trackInfo, setTrackInfo] =
    useState<TrackInfoResponse | null>(null)
  const [trackInfoRefreshing, setTrackInfoRefreshing] =
    useState(false)
  const trackInfoPollRef = useRef<
    ReturnType<typeof setTimeout> | null
  >(null)
  const activeTrackRequestRef = useRef(0)
  const [isAdmin, setIsAdmin] = useState(() => getIsAdmin())
  const [debugMode, setDebugMode] = useState(false)

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
  const [shareCopyBusy, setShareCopyBusy] = useState(false)
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
  const [albumTrackSearch, setAlbumTrackSearch] = useState('')
  const [albumSearchResults, setAlbumSearchResults] = useState<Track[]>([])
  const [albumSearchLoading, setAlbumSearchLoading] = useState(false)
  const [videoReady, setVideoReady] =
    useState(false)
  const videoEnabled =
    localStorage.getItem('setting-video-enabled') !== 'false'

  const sheetRef = useRef<HTMLDivElement>(null)
  const coverInputRef =
    useRef<HTMLInputElement>(null)
  const videoInputRef =
    useRef<HTMLInputElement>(null)
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
    let cancelled = false
    api.getAuthConfig()
      .then((cfg) => {
        if (!cancelled) {
          setDebugMode(Boolean(cfg.debug))
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return
    }
    const mq = window.matchMedia('(pointer: coarse)')
    const apply = () => setIsCoarsePointer(mq.matches)
    apply()
    mq.addEventListener('change', apply)
    return () => {
      mq.removeEventListener('change', apply)
    }
  }, [])

  useEffect(() => {
    if (!isCardOpen || !track) {
      activeTrackRequestRef.current += 1
      setExtrasOpen(false)
      setCard(null)
      setShowLyrics(false)
      setShowTrackInfo(false)
      setEditingLyrics(false)
      setShowEdit(false)
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
    void api.syncSessionUserFlags().finally(() => {
      setIsAdmin(getIsAdmin())
    })
    setCoverVer((v) => v + 1)
    setCoverFailed(false)
    setShowEdit(false)
    setVideoReady(false)
    setLoading(true)
    const requestId = activeTrackRequestRef.current + 1
    activeTrackRequestRef.current = requestId
    api
      .getTrackCard(track.id)
      .then((c) => {
        if (activeTrackRequestRef.current !== requestId) {
          return
        }
        setCard(c)
      })
      .catch(() => {})
      .finally(() => {
        if (activeTrackRequestRef.current !== requestId) {
          return
        }
        setLoading(false)
      })

    setSimilarTracks([])
    api.getSimilarTracks(track.id)
      .then((r) => {
        if (activeTrackRequestRef.current !== requestId) {
          return
        }
        setSimilarTracks(r.tracks)
      })
      .catch(() => {})

    setTrackInfo(null)
    let cancelled = false
    let attempts = 0
    const pollInfo = async () => {
      try {
        const data = await api.getTrackInfo(track.id)
        if (
          cancelled ||
          activeTrackRequestRef.current !== requestId
        ) {
          return
        }
        setTrackInfo(data)
        if (
          showTrackInfo &&
          (data.status === 'fetching' || data.status === 'pending') &&
          attempts < 30
        ) {
          attempts += 1
          trackInfoPollRef.current = setTimeout(pollInfo, 3000)
        }
      } catch {
        // silent - info block hidden if not loadable
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
  }, [isCardOpen, track?.id, showTrackInfo])

  useEffect(() => {
    const albumFromCard = card?.album
    if (albumFromCard) {
      setRelatedAlbumInfo({
        id: albumFromCard.id,
        title: albumFromCard.title,
      })
      return
    }
    const fallbackAlbumId = track?.album_id
    if (!fallbackAlbumId) {
      setRelatedAlbumInfo(null)
      return
    }
    setRelatedAlbumInfo((prev) => (
      prev?.id === fallbackAlbumId
        ? prev
        : {
            id: fallbackAlbumId,
            title: `Альбом #${fallbackAlbumId}`,
          }
    ))
    let cancelled = false
    api.getAlbum(fallbackAlbumId).then((album) => {
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
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') setExtrasOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
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

  const handleBackdrop = (
    e: React.MouseEvent,
  ) => {
    if (e.target === e.currentTarget) closeCard()
  }

  const formatShareChatTitle = useCallback((item: ChatListItem): string => {
    if (item.conversation.type === 'saved') {
      return t('redesign.chats.savedTitle')
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
    return t('redesign.chats.chatNumber', {
      id: item.conversation.id,
    })
  }, [t])

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
      setShareError('Не удалось загрузить чаты')
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
      sound.play('notificationSuccess')
      showIsland({
        kind: 'toast',
        title: t('trackSheet.shareSent'),
        durationMs: 2200,
      })
    } catch {
      setShareError('Не удалось отправить')
      sound.play('notificationError')
    } finally {
      setShareSendingConvId(null)
    }
  }, [sharePayload, sound])

  const handleCopyShare = useCallback(async () => {
    if (!sharePayload) return
    setShareCopyBusy(true)
    try {
      if (sharePayload.type === 'track') {
        const links = await api.getShareLinks(sharePayload.id)
        await navigator.clipboard.writeText(links.url)
      } else {
        const base = `${window.location.origin}${import.meta.env.BASE_URL}`
        const path = sharePayload.type === 'album'
          ? `library?shareType=album&id=${sharePayload.id}`
          : `playlists?shareType=playlist&id=${sharePayload.id}`
        await navigator.clipboard.writeText(`${base}${path}`)
      }
      sound.play('notificationInfo')
      showIsland({
        kind: 'toast',
        title: t('trackSheet.linkCopied'),
        durationMs: 2000,
      })
    } catch {
      setShareError('Не удалось скопировать')
      sound.play('notificationError')
    } finally {
      setShareCopyBusy(false)
    }
  }, [sharePayload, sound])

  const openAlbumEditor = useCallback(async () => {
    const albumId = relatedAlbumInfo?.id ?? track?.album_id ?? null
    const internalId = getInternalUserId()
    const canOwnerEdit = Boolean(
      internalId !== null &&
      track?.uploaded_by_id === internalId,
    )
    if (
      !albumId ||
      (!isAdmin && !debugMode && !import.meta.env.DEV && !canOwnerEdit)
    ) {
      return
    }
    setAlbumEditBusy(true)
    try {
      const [album, myLib] = await Promise.all([
        api.getAlbum(albumId),
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
      showIsland({
        kind: 'error',
        title: t('trackSheet.albumEditorError'),
        durationMs: 4000,
      })
    } finally {
      setAlbumEditBusy(false)
    }
  }, [relatedAlbumInfo?.id, track?.album_id, isAdmin, debugMode, track?.uploaded_by_id, t])

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
    if (!albumEditData || (!isAdmin && !debugMode)) return
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
    debugMode,
    refreshAlbumEditor,
  ])

  const removeAlbumTrack = useCallback(async (trackId: number) => {
    if (!albumEditData || (!isAdmin && !debugMode)) return
    await api.removeTrackFromAlbum(albumEditData.id, trackId)
    await refreshAlbumEditor()
  }, [albumEditData?.id, isAdmin, debugMode, refreshAlbumEditor])

  const addAlbumTrack = useCallback(async () => {
    if (!albumEditData || (!isAdmin && !debugMode) || !albumAddTrackId) return
    await api.addTrackToAlbum(albumEditData.id, albumAddTrackId)
    setAlbumAddTrackId(null)
    await refreshAlbumEditor()
  }, [albumEditData?.id, isAdmin, debugMode, albumAddTrackId, refreshAlbumEditor])

  const moveAlbumTrack = useCallback(async (index: number, dir: -1 | 1) => {
    if (!albumEditData || (!isAdmin && !debugMode)) return
    const nextIndex = index + dir
    if (nextIndex < 0 || nextIndex >= albumEditData.tracks.length) return
    const ids = albumEditData.tracks.map((t) => t.id)
    const tmp = ids[index]
    ids[index] = ids[nextIndex]
    ids[nextIndex] = tmp
    await api.setAlbumTrackOrder(albumEditData.id, ids)
    await refreshAlbumEditor()
  }, [albumEditData?.id, albumEditData?.tracks, isAdmin, debugMode, refreshAlbumEditor])

  const saveAlbumTrackTitle = useCallback(async (trackId: number) => {
    if (!isAdmin && !debugMode) return
    const raw = albumTrackTitleDrafts[trackId]
    const title = raw?.trim()
    if (!title) return
    await api.updateTrack(trackId, { title })
    await refreshAlbumEditor()
  }, [isAdmin, debugMode, albumTrackTitleDrafts, refreshAlbumEditor])

  useEffect(() => {
    if (!albumEditOpen || !albumEditData) return
    const q = albumTrackSearch.trim()
    if (!q) {
      setAlbumSearchResults([])
      setAlbumSearchLoading(false)
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      setAlbumSearchLoading(true)
      api.getTracks({ q, size: 30, page: 1 })
        .then((res) => {
          if (!cancelled) {
            setAlbumSearchResults(res.items)
          }
        })
        .catch(() => {
          if (!cancelled) {
            setAlbumSearchResults([])
          }
        })
        .finally(() => {
          if (!cancelled) {
            setAlbumSearchLoading(false)
          }
        })
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [albumEditOpen, albumEditData?.id, albumTrackSearch])

  const handleAuthor = () => {
    if (track?.artist && onOpenArtist) {
      goToArtist(track.artist)
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

  const playbackVariants = useMemo((): TrackPlaybackVariantBrief[] => {
    if (!track) return []
    const fromTrack = track.playback_variants
    if (fromTrack && fromTrack.length > 0) return fromTrack
    return card?.playback_variants ?? []
  }, [track, card])
  const pct = duration
    ? (smoothCurrentTime / duration) * 100
    : 0
  const displayPct = Math.max(0, Math.min(100, pct))

  useEffect(() => {
    setSmoothCurrentTime(currentTime)
  }, [currentTime, track?.id])

  useEffect(() => {
    if (!isPlaying) {
      setSmoothCurrentTime(currentTime)
      return
    }
    let rafId = 0
    const frame = () => {
      setSmoothCurrentTime(getPreciseTime())
      rafId = window.requestAnimationFrame(frame)
    }
    rafId = window.requestAnimationFrame(frame)
    return () => {
      window.cancelAnimationFrame(rafId)
    }
  }, [currentTime, getPreciseTime, isPlaying, track?.id])

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
  const canEditUi =
    isAdmin || debugMode || import.meta.env.DEV
  const liked = isLiked(track.id)
  const disliked = isDisliked(track.id)

  const hasActiveVideo =
    !!videoSrc && videoEnabled
  const visualMode =
    showLyrics || hasActiveVideo
  const perfLite =
    isCoarsePointer ||
    (typeof document !== 'undefined' &&
      document.body.classList.contains('ds-perf-lite'))
  const useRichCoverVisuals = !perfLite && isPlaying

  return (
    <div
      className={`tcs-backdrop${exit.cls}`}
      onClick={handleBackdrop}
    >
      <m.div
        className={`tcs-sheet re-tcs-sheet${hasActiveVideo ? ' tcs-video-mode' : ''}${exit.cls}`}
        ref={sheetRef}
        drag={reduce || isCoarsePointer ? false : 'y'}
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={0.18}
        dragMomentum={false}
        onDragEnd={handleSheetDragEnd}
      >
        <div
          className="tcs-handle re-tcs-handle"
          aria-label={t('redesign.tracks.tcsCloseAria')}
          aria-hidden="true"
        />
        <MotionPress
          type="button"
          variant="icon"
          className="tcs-close"
          ariaLabel={t('trackSheet.close')}
          haptic="light"
          onClick={closeCard}
        >
          <Icon name="x" size={22} />
        </MotionPress>

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
                    showIsland({
                      kind: 'toast',
                      title: t('trackSheet.pipUnavailable'),
                      durationMs: 3000,
                    })
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
          <div className="tcs-cover-wrap re-tcs-wrap">
            {coverBusy && (
              <div className="tcs-cover-loading">
                <div className="loader" />
              </div>
            )}
            {coverSrc && !coverFailed ? (
              <div className="re-tcs-cover-stack">
                {useRichCoverVisuals ? (
                  <AmbientStage
                    coverUrl={coverSrc}
                    className="re-tcs-ambient"
                  >
                    <KenBurnsCover
                      src={coverSrc}
                      alt=""
                      duration={20}
                      className="re-tcs-kb"
                    />
                  </AmbientStage>
                ) : (
                  <img
                    src={coverSrc}
                    alt=""
                    className="re-tcs-cover-probe"
                    loading="lazy"
                  />
                )}
                <img
                  src={coverSrc}
                  alt=""
                  className="re-tcs-cover-probe"
                  onError={() => setCoverFailed(true)}
                  aria-hidden
                />
              </div>
            ) : (
              <div className="tcs-cover-placeholder">
                <Icon name="music" size={72} />
              </div>
            )}
            {useRichCoverVisuals && (
              <div className="tcs-cover-wave-area" aria-hidden>
                <div className="tcs-cover-wave-gradient" />
                <Waveform
                  overlay
                  height={64}
                  bars={perfLite ? 18 : 36}
                  className="tcs-cover-waveform"
                />
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
                isOwner={isOwner || canEditUi}
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
                isOwner={isOwner || canEditUi}
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
                  {track.artist ?? '—'}
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
              {(canEditUi && (relatedAlbumInfo || track.album_id)) && (
                <button
                  className="icon-btn"
                  onClick={() => {
                    void openAlbumEditor()
                  }}
                  disabled={albumEditBusy}
                  aria-label="Редактировать альбом"
                >
                  <Icon name="edit" size={18} />
                </button>
              )}
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
                {(canEditUi && (relatedAlbumInfo || track.album_id)) && (
                  <button
                    className="icon-btn"
                    onClick={() => {
                      void openAlbumEditor()
                    }}
                    disabled={albumEditBusy}
                    aria-label="Редактировать альбом"
                  >
                    <Icon name="edit" size={18} />
                  </button>
                )}
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
                {track.artist ?? '—'}
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
          {track.last_listen_at && (
            <p className="tcs-last-listen">
              {typeof track.last_listen_seconds === 'number' &&
              track.last_listen_seconds >= 1
                ? t('trackSheet.lastListenWhenAndDur', {
                    when: fmtListenWhen(
                      track.last_listen_at,
                    ),
                    duration: fmt(
                      track.last_listen_seconds,
                    ),
                  })
                : t('trackSheet.lastListenWhenOnly', {
                    when: fmtListenWhen(
                      track.last_listen_at,
                    ),
                  })}
            </p>
          )}
          {(relatedAlbumInfo || track.album_id) && (
            <div className="tcs-share-related-row">
              <span className="tcs-share-related-title">
                Альбом: {
                  relatedAlbumInfo?.title
                  ?? `#${track.album_id}`
                }
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="tcs-share-related-btn"
                  onClick={() => {
                    const albumId = relatedAlbumInfo?.id ?? track.album_id
                    if (!albumId) return
                    void openShareModal({
                      id: albumId,
                      type: 'album',
                      title: relatedAlbumInfo?.title ?? `Альбом #${albumId}`,
                    })
                  }}
                >
                  <Icon name="share" size={14} />
                  Поделиться
                </button>
                {canEditUi && (
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
        </div>
        </div>

        <div className="tcs-player-controls">
          <div className="tcs-seek-wrap">
            {track.waveform_data && track.waveform_data.length > 0 ? (
              <WaveformBar
                data={track.waveform_data}
                progress={displayPct}
                onSeek={seek}
                height={40}
                className="tcs-waveform-bar"
                durationSec={duration}
              />
            ) : (
            <input
              type="range"
              className="tcs-seek"
              min={0}
              max={100}
              step={0.1}
              value={displayPct}
              onChange={(e) =>
                seek(Number(e.target.value))
              }
              style={{ ['--progress' as string]: `${displayPct}%` }}
            />
            )}
            <div className="tcs-time">
              <span>{fmt(smoothCurrentTime)}</span>
              <span>{fmt(duration)}</span>
            </div>
          </div>
          <div className="tcs-play-row">
            <MotionPress
              type="button"
              variant="icon"
              className="ctrl-btn"
              ariaLabel={t('trackSheet.seekBack')}
              haptic="light"
              onClick={() => skipBackward(15)}
            >
              <Icon name="rewind-5" size={22} />
            </MotionPress>
            <MotionPress
              type="button"
              variant="icon"
              className="ctrl-btn"
              ariaLabel={t('redesign.player.prevAria')}
              haptic="light"
              onClick={playPrev}
            >
              <Icon name="skip-back" size={22} />
            </MotionPress>
            <MotionPress
              type="button"
              variant="primary"
              className={`play-btn re-tcs-play${
                isPlaying ? ' play-btn--playing' : ''
              }`}
              ariaLabel={
                isPlaying
                  ? t('redesign.player.pauseAria')
                  : t('redesign.player.playAria')
              }
              haptic="medium"
              onClick={togglePlay}
            >
              <MorphIcon
                name={isPlaying ? 'pause' : 'play'}
                size={20}
                filled
              />
            </MotionPress>
            <MotionPress
              type="button"
              variant="icon"
              className="ctrl-btn"
              ariaLabel={t('redesign.player.nextAria')}
              haptic="light"
              onClick={playNext}
            >
              <Icon name="skip-forward" size={22} />
            </MotionPress>
            <MotionPress
              type="button"
              variant="icon"
              className="ctrl-btn"
              ariaLabel={t('trackSheet.seekForward')}
              haptic="light"
              onClick={() => skipForward(15)}
            >
              <Icon name="forward-5" size={22} />
            </MotionPress>
          </div>
        </div>

        <div
          className={`tcs-actions${editingLyrics ? ' tcs-dimmed' : ''}`}
        >
          <MotionPress
            type="button"
            variant="ghost"
            className={`tcs-action-btn${liked ? ' active' : ''}`}
            haptic={liked ? 'light' : 'medium'}
            onClick={() => toggleLike(track.id)}
          >
            <MorphIcon
              name="heart"
              size={20}
              filled={liked}
            />
            <span className="tcs-action-label">
              {t('trackSheet.like')}
            </span>
          </MotionPress>

          <MotionPress
            type="button"
            variant="ghost"
            className={`tcs-action-btn${disliked ? ' active' : ''}`}
            haptic="light"
            onClick={() => toggleDislike(track.id)}
          >
            <Icon name="thumbs-down" size={20} />
            <span className="tcs-action-label">
              {t('trackSheet.dislike')}
            </span>
          </MotionPress>

          {(Boolean(card?.has_lyrics) ||
            isOwner ||
            canEditUi) && (
            <MotionPress
              type="button"
              variant="ghost"
              className={`tcs-action-btn${showLyrics ? ' active' : ''}`}
              haptic="light"
              onClick={() => {
                setShowLyrics((v) => !v)
                setEditingLyrics(false)
              }}
            >
              <Icon name="text" size={20} />
              <span className="tcs-action-label">
                {t('trackSheet.lyrics')}
              </span>
            </MotionPress>
          )}

          <MotionPress
            type="button"
            variant="ghost"
            className="tcs-action-btn"
            haptic="light"
            onClick={() => {
              void startRadio(track).catch(() => {
                showIsland({
                  kind: 'error',
                  title: t('redesign.home.radioError'),
                  durationMs: 3000,
                })
              })
            }}
          >
            <Icon name="radio" size={20} />
            <span className="tcs-action-label">
              {t('trackSheet.radioFromTrack')}
            </span>
          </MotionPress>

          <MotionPress
            type="button"
            variant="ghost"
            className="tcs-action-btn"
            haptic="light"
            disabled={!track?.artist}
            onClick={handleAuthor}
          >
            <Icon name="user" size={20} />
            <span className="tcs-action-label">
              {t('trackSheet.toAuthor')}
            </span>
          </MotionPress>

          {canEditUi && (
            <MotionPress
              type="button"
              variant="ghost"
              className={`tcs-action-btn${showEdit ? ' active' : ''}`}
              haptic="light"
              onClick={() => setShowEdit((v) => !v)}
            >
              <Icon name="edit" size={20} />
              <span className="tcs-action-label">
                {t('trackSheet.edit')}
              </span>
            </MotionPress>
          )}

          <MotionPress
            type="button"
            variant="ghost"
            className="tcs-action-btn"
            haptic="light"
            onClick={openComplaint}
          >
            <Icon name="flag" size={20} />
            <span className="tcs-action-label">
              {t('trackSheet.complaint')}
            </span>
          </MotionPress>
        </div>

        {extrasOpen && (
          <div
            className="tcs-extras-overlay"
            onClick={() => setExtrasOpen(false)}
            role="presentation"
          >
            <div
              className="tcs-extras-sheet"
              id="tcs-extras-sheet"
              role="dialog"
              aria-modal="true"
              aria-label={t('trackSheet.moreMenu')}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="tcs-extras-sheet-header">
                <span>{t('trackSheet.moreMenu')}</span>
                <button
                  type="button"
                  className="tcs-extras-close"
                  onClick={() =>
                    setExtrasOpen(false)
                  }
                  aria-label={t('common.close', 'Закрыть')}
                >
                  <Icon name="x" size={16} />
                </button>
              </div>
              <div className="tcs-extras-section">
                <div className="tcs-extras-title">
                  {t('trackSheet.queue')}
                </div>
                <div className="pb-extras">
                  <button
                    type="button"
                    className="pb-extras-btn"
                    onClick={() => {
                      setExtrasOpen(false)
                      openQueue()
                    }}
                    aria-label={t('trackSheet.queue')}
                  >
                    <Icon name="queue" size={14} />
                    {t('trackSheet.queue')}
                  </button>
                </div>
              </div>

              <div className="tcs-extras-section">
                <div className="tcs-extras-title">
                  {t(
                    'trackSheet.playbackSpeed',
                    'Скорость',
                  )}
                </div>
                <div className="pb-extras">
                  {SPEED_OPTIONS.map((rate) => (
                    <button
                      type="button"
                      key={rate}
                      className={`pb-extras-btn${playbackRate === rate ? ' active' : ''}`}
                      onClick={() =>
                        setPlaybackRate(rate)
                      }
                      aria-pressed={
                        playbackRate === rate
                      }
                    >
                      {rate}×
                    </button>
                  ))}
                </div>
              </div>

              <div className="tcs-extras-section">
                <div className="tcs-extras-title">
                  AB loop
                </div>
                <div className="pb-extras">
                  <button
                    type="button"
                    className={`pb-extras-btn${abLoop.a !== null ? ' active' : ''}`}
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
                      onClick={clearAbLoop}
                      title={t('trackSheet.abReset')}
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>

              <div className="tcs-extras-section">
                <div className="tcs-extras-title">
                  {t(
                    'trackSheet.sleepTimer',
                    'Sleep timer',
                  )}
                </div>
                <div className="pb-extras">
                  <span className="tcs-extras-sleep-state">
                    <Icon name="moon" size={12} />
                    {sleepMode === 'minutes' &&
                    sleepRemainingSec > 0
                      ? `${Math.floor(
                          sleepRemainingSec / 60,
                        )}:${String(
                          sleepRemainingSec % 60,
                        ).padStart(2, '0')}`
                      : sleepMode === 'end-of-track'
                        ? t(
                            'trackSheet.sleepEot',
                            'Конец трека',
                          )
                        : t(
                            'trackSheet.sleepOff',
                            'Сон',
                          )}
                  </span>
                  {[15, 30, 60].map((m) => (
                    <button
                      key={m}
                      type="button"
                      className={`pb-extras-btn${
                        sleepMode === 'minutes' &&
                        Math.ceil(sleepRemainingSec / 60) === m
                          ? ' active'
                          : ''
                      }`}
                      onClick={() => setSleepTimerMinutes(m)}
                    >
                      {m}м
                    </button>
                  ))}
                  <button
                    type="button"
                    className={`pb-extras-btn${
                      sleepMode === 'end-of-track'
                        ? ' active'
                        : ''
                    }`}
                    onClick={setSleepTimerEndOfTrack}
                    title={t(
                      'trackSheet.sleepEotTitle',
                      'Стоп после текущего трека',
                    )}
                  >
                    EOT
                  </button>
                  {sleepMode !== 'off' && (
                    <button
                      type="button"
                      className="pb-extras-btn"
                      onClick={cancelSleepTimer}
                      title={t(
                        'trackSheet.sleepCancel',
                        'Выключить таймер сна',
                      )}
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {showEdit && canEditUi && (
          <div className="tcs-edit-panel">
            <div className="tcs-edit-title">
              {t('trackSheet.editing')}
            </div>
            <div className="tcs-edit-actions">
              {canEditUi && (
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
          (isOwner || canEditUi) && (
          <div className="tcs-lyrics-edit-inline">
            <LyricsPanel
              trackId={track.id}
              isOwner={isOwner || canEditUi}
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
              {t('trackSheet.playbackSource', 'Источник')}
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
                      showIsland({
                        kind: 'error',
                        title: t('trackSheet.sourceSwitchError'),
                        durationMs: 3500,
                      })
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

        {((track.source_url || track.sc_url) ||
          track.access_mode === 'third_party_stream') && (
          <div className="tcs-source-info">
            {track.access_mode === 'third_party_stream' && (
              <p className="tcs-access-mode-line">
                {t('trackCard.accessStream')}
              </p>
            )}
            {(track.source_url || track.sc_url) && (
              <>
                <span className="tcs-source-label">
                  {t('trackSheet.source')}{' '}
                  <a
                    href={
                      track.source_url || track.sc_url || '#'
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {track.source_name || track.source}
                  </a>
                </span>
                <p className="tcs-disclaimer">
                  {track.access_mode ===
                  'third_party_stream'
                    ? t('trackSheet.disclaimerStream')
                    : t('trackSheet.disclaimerMeta')}
                </p>
              </>
            )}
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
                      showIsland({
                        kind: 'error',
                        title: t('trackSheet.streamDebugInvalid'),
                        durationMs: 3500,
                      })
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

        {showTrackInfo && (
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
                      {trackInfo?.status ?? '—'}
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
              trackInfoRefreshing ||
              !trackInfo) && (
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
                    <span className="tcs-similar-track-title" dir="auto">
                      {st.title}
                      {st.artist ? (
                        <span className="tcs-similar-track-artist">
                          {' · '}
                          {st.artist}
                        </span>
                      ) : null}
                    </span>
                    <span
                      className="tcs-similar-track-meta"
                      dir="auto"
                    >
                      {buildTrackCardSummaryLine(st, t)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
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
              {
                hapticTick()
                setVolume(
                  parseFloat(e.target.value),
                )
              }
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
                <input
                  className="form-input"
                  placeholder="Поиск треков: название или артист..."
                  value={albumTrackSearch}
                  onChange={(e) => setAlbumTrackSearch(e.target.value)}
                  style={{ minWidth: 220 }}
                />
                <select
                  className="form-input"
                  value={albumAddTrackId ?? ''}
                  onChange={(e) => setAlbumAddTrackId(Number(e.target.value) || null)}
                >
                  <option value="">Добавить трек...</option>
                  {(() => {
                    const inAlbum = new Set(albumEditData.tracks.map((at) => at.id))
                    const q = albumTrackSearch.trim().toLowerCase()
                    const local = albumTrackPool
                      .filter((t) => !inAlbum.has(t.id))
                      .filter((t) => {
                        if (!q) return true
                        const hay = `${t.title} ${t.artist ?? ''}`.toLowerCase()
                        return hay.includes(q)
                      })
                    const merged = [...local]
                    for (const remote of albumSearchResults) {
                      if (
                        !inAlbum.has(remote.id) &&
                        !merged.some((t) => t.id === remote.id)
                      ) {
                        merged.push(remote)
                      }
                    }
                    return merged.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.title} {t.artist ? `- ${t.artist}` : ''}
                      </option>
                    ))
                  })()}
                </select>
                <button className="btn-secondary" onClick={() => void addAlbumTrack()}>
                  Добавить
                </button>
              </div>
              {albumSearchLoading && (
                <p className="hint" style={{ marginTop: 8 }}>Идёт поиск…</p>
              )}
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
                      ? 'Поделиться альбомом'
                      : sharePayload?.type === 'playlist'
                        ? 'Поделиться плейлистом'
                        : 'Поделиться треком'}
                  </h3>
                  <p className="share-modal-subtitle">
                    {sharePayload?.title || 'Выберите чат для отправки'}
                  </p>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => {
                    void handleCopyShare()
                  }}
                  aria-label="Скопировать ссылку"
                  disabled={shareCopyBusy}
                >
                  <Icon name="copy" size={16} />
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShareOpen(false)}
                  aria-label="Закрыть"
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
                  Нет доступных чатов
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
                          {sending ? 'Отправка...' : 'Отправить'}
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
      </m.div>
    </div>
  )
}



