import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ArtistAvatarViewer } from '@/components/ArtistView/ArtistAvatarViewer'
import { ArtistCatalogReleasePanel } from '@/components/ArtistView/ArtistCatalogReleasePanel'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { TrackList } from '@/components/TrackList/TrackList'
import { api, getApiErrorMessage } from '@/lib/api'
import {
  getIsAdmin,
  getInternalUserId,
  haptic,
  hapticNotification,
} from '@/lib/telegram'
import { showIsland } from '@/lib/island'
import { coverProxyUrl } from '@/lib/coverProxy'
import { queueMutation } from '@/lib/pendingEvents'
import { usePrefetchTracks } from '@/store/PrefetchContext'

function _isNetworkError(e: unknown): boolean {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return true
  }
  return (
    e instanceof TypeError &&
    typeof e.message === 'string' &&
    /fetch|network/i.test(e.message)
  )
}
import type {
  ArtistCatalogReleaseSummary,
  ArtistDetail,
  ArtistInfo,
  ArtistListenersResponse,
  ArtistSourceProfile,
  ArtistSupplementalResponse,
  DiscographyItem,
  Track,
} from '@/types/api'

interface Props {
  artistId: number
  onClose: () => void
  onSelectSimilarArtist?: (id: number) => void
}

interface ArtistViewData {
  source_id: string | null
  source_name: string | null
  source_page_url: string | null
  bio: string | null
  birth_date: string | null
  birthplace: string | null
  country: string | null
  image_url: string | null
  website_url: string | null
  discography: DiscographyItem[]
}

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function monthlyListenersText(count: number): string {
  const n = Math.abs(Math.trunc(count))
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) {
    return 'уникальный слушатель за месяц'
  }
  if (
    mod10 >= 2 &&
    mod10 <= 4 &&
    !(mod100 >= 12 && mod100 <= 14)
  ) {
    return 'уникальных слушателя за месяц'
  }
  return 'уникальных слушателей за месяц'
}

const MONTH_LABELS = [
  'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек',
]

function ArtistListenersChart({
  history,
}: {
  history: {
    year: number
    month: number
    unique_listeners: number
    total_plays?: number
    total_likes?: number
    total_followers?: number
  }[]
}) {
  const sorted = [...history]
    .sort((a, b) =>
      a.year !== b.year
        ? a.year - b.year
        : a.month - b.month,
    )
    .slice(-12)

  const max = Math.max(
    1,
    ...sorted.map((r) => r.unique_listeners),
  )

  return (
    <div className="artist-listeners-chart">
      {sorted.map((r) => {
        const lines = [
          `${MONTH_LABELS[r.month - 1]} ${r.year}: ${fmtCount(r.unique_listeners)}`,
          r.total_plays ? `${fmtCount(r.total_plays)} прослушиваний` : null,
          r.total_likes ? `${fmtCount(r.total_likes)} лайков` : null,
        ]
          .filter(Boolean)
          .join('\n')
        return (
          <div
            key={`${r.year}-${r.month}`}
            className="artist-listeners-bar-col"
            title={lines}
          >
            <div className="artist-listeners-bar-wrap">
              <div
                className="artist-listeners-bar"
                style={{
                  height: `${Math.round(
                    (r.unique_listeners / max) * 100,
                  )}%`,
                }}
              />
            </div>
            <span className="artist-listeners-bar-label">
              {MONTH_LABELS[r.month - 1]}
            </span>
            <span className="artist-listeners-bar-value">
              {fmtCount(r.unique_listeners)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function hasAnyInfo(view: ArtistViewData): boolean {
  return Boolean(
    view.bio ||
      view.birth_date ||
      view.birthplace ||
      view.country ||
      view.website_url ||
      view.discography.length > 0,
  )
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value
    ? value
    : null
}

function buildMergedView(
  artist: ArtistDetail,
): ArtistViewData {
  return {
    source_id: artist.primary_source_id ?? null,
    source_name: null,
    source_page_url: null,
    bio: artist.bio,
    birth_date: artist.birth_date,
    birthplace: artist.birthplace,
    country: artist.country,
    image_url: artist.image_url,
    website_url: artist.website_url,
    discography: Array.isArray(artist.discography)
      ? (artist.discography as DiscographyItem[])
      : [],
  }
}

function buildProfileView(
  profile: ArtistSourceProfile,
  fallbackImage: string | null,
): ArtistViewData {
  return {
    source_id: profile.source_id,
    source_name: profile.source_name,
    source_page_url: profile.source_page_url ?? null,
    bio: asString(profile.bio),
    birth_date: asString(profile.birth_date),
    birthplace: asString(profile.birthplace),
    country: asString(profile.country),
    image_url:
      asString(profile.image_url) || fallbackImage,
    website_url: asString(profile.website_url),
    discography: Array.isArray(profile.discography)
      ? profile.discography
      : [],
  }
}

function buildPlatformSupplementalView(
  artist: ArtistDetail,
  supplemental: ArtistSupplementalResponse | null,
): ArtistViewData | null {
  if (!supplemental || supplemental.status !== 'done' || !supplemental.content) {
    return null
  }
  return {
    source_id: 'platform',
    source_name: 'Платформа',
    source_page_url: null,
    bio: supplemental.content,
    birth_date: null,
    birthplace: null,
    country: null,
    image_url: artist.image_url,
    website_url: null,
    discography: [],
  }
}

function computeAge(iso: string | null): number | null {
  if (!iso) return null
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  const year = Number(m[1])
  const month = Number(m[2])
  const day = Number(m[3])
  const now = new Date()
  let age = now.getUTCFullYear() - year
  const beforeBirthday =
    now.getUTCMonth() + 1 < month ||
    (now.getUTCMonth() + 1 === month &&
      now.getUTCDate() < day)
  if (beforeBirthday) age -= 1
  return age >= 0 ? age : null
}

function cleanWikiText(s: string | null): string | null {
  if (!s) return null
  const cleaned = s
    .replace(/\{\{[^}]*\}\}/g, '')
    .replace(/\[\[(?:[^\]|]+)\|([^\]]+)\]\]/g, '$1')
    .replace(/\[\[([^\]]+)\]\]/g, '$1')
    .replace(/[{}\[\]|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned || null
}

function artistImageUrl(imageKey: string | null): string | null {
  if (!imageKey) return null
  return coverProxyUrl(imageKey, { width: 480 })
}

const stageProgress: Record<string, number> = {
  queued: 5,
  searching: 20,
  processing: 50,
  saving: 85,
  done: 100,
  not_found: 100,
  error: 100,
}

export function ArtistProfileStandalone({
  artistId,
  onClose,
  onSelectSimilarArtist,
}: Props) {
  const { t } = useTranslation()
  const [artist, setArtist] =
    useState<ArtistDetail | null>(null)
  const [tracks, setTracks] = useState<
    Track[] | null
  >(null)
  usePrefetchTracks(tracks ?? null, 'artist')
  const [bioOpen, setBioOpen] = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [enrichError, setEnrichError] = useState<
    string | null
  >(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugStage, setDebugStage] =
    useState<string | null>(null)
  const [debugLogs, setDebugLogs] = useState<
    string[]
  >([])
  const [debugRunning, setDebugRunning] =
    useState(false)
  const [debugTaskId, setDebugTaskId] =
    useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [selectedSourceId, setSelectedSourceId] =
    useState<string | null>(null)
  const [avatarOpen, setAvatarOpen] = useState(false)
  const [supplemental, setSupplemental] =
    useState<ArtistSupplementalResponse | null>(null)
  const [similarArtists, setSimilarArtists] = useState<
    ArtistInfo[] | null
  >(null)
  const [catalogReleases, setCatalogReleases] = useState<
    ArtistCatalogReleaseSummary[] | null
  >(null)
  const [catalogReleasesError, setCatalogReleasesError] =
    useState(false)
  const [selectedReleaseId, setSelectedReleaseId] = useState<
    number | null
  >(null)
  const [following, setFollowing] = useState<
    boolean | null
  >(null)
  const [followLoading, setFollowLoading] =
    useState(false)
  const [listeners, setListeners] =
    useState<ArtistListenersResponse | null>(null)
  const [listenersOpen, setListenersOpen] =
    useState(false)
  const [similarCanPrev, setSimilarCanPrev] = useState(false)
  const [similarCanNext, setSimilarCanNext] = useState(false)
  const supplementalPollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const similarRowRef = useRef<HTMLDivElement>(null)
  const [snippetPlaying, setSnippetPlaying] = useState(false)
  const [snippetIndex, setSnippetIndex] = useState(0)
  const isAdmin = getIsAdmin()
  const currentUserId = getInternalUserId()

  useEffect(() => {
    if (!debugRunning) return
    setElapsed(0)
    const iv = setInterval(
      () => setElapsed((e) => e + 1),
      1000,
    )
    return () => clearInterval(iv)
  }, [debugRunning])

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({
        behavior: 'smooth',
      })
    }
  }, [debugLogs])

  const handleSnippetEnded = () => {
    if (!tracks || !tracks.length) return
    const nextIdx = (snippetIndex + 1) % tracks.length
    setSnippetIndex(nextIdx)
    // Play next automatically, should be allowed since it's chained from an ended event (user previously interacted)
    if (audioRef.current) {
      // Need a slight delay to ensure src updates
      setTimeout(() => {
        if (snippetPlaying && audioRef.current) {
          audioRef.current.play().catch(() => setSnippetPlaying(false))
        }
      }, 50)
    }
  }

  const toggleSnippet = () => {
    if (!audioRef.current) return
    if (snippetPlaying) {
      audioRef.current.pause()
      setSnippetPlaying(false)
    } else {
      setSnippetPlaying(true)
      audioRef.current.play().catch(() => setSnippetPlaying(false))
    }
  }

  useEffect(() => {
    let cancelled = false
    setArtist(null)
    setTracks(null)
    setBioOpen(false)
    setSelectedSourceId(null)
    setAvatarOpen(false)
    setSupplemental(null)
    setSimilarArtists(null)
    setCatalogReleases(null)
    setCatalogReleasesError(false)
    setSelectedReleaseId(null)
    setFollowing(null)
    setListeners(null)
    setListenersOpen(false)
    setSnippetPlaying(false)
    setSnippetIndex(0)
    try {
      audioRef.current?.pause()
    } catch {
      /* ignore */
    }

    api
      .getArtist(artistId)
      .then((data) => {
        if (!cancelled) setArtist(data)
      })
      .catch(() => {
        if (!cancelled) setArtist(null)
      })
    api
      .getArtistTracks(artistId)
      .then((res) => {
        if (!cancelled) setTracks(res.items)
      })
      .catch(() => {
        if (!cancelled) setTracks([])
      })
    api
      .getArtistSupplemental(artistId)
      .then((data) => {
        if (!cancelled) {
          setSupplemental(data)
          if (data.status === 'fetching' || data.status === 'pending') {
            startSupplementalPoll(artistId, 0, () => cancelled)
          }
        }
      })
      .catch(() => { /* supplemental is optional */ })

    api
      .listSimilarCatalogArtists(artistId, 10)
      .then((res) => {
        if (!cancelled) setSimilarArtists(res.items)
      })
      .catch(() => {
        if (!cancelled) setSimilarArtists([])
      })

    api
      .listArtistCatalogReleases(artistId)
      .then((res) => {
        if (!cancelled) {
          setCatalogReleases(res.items)
          setCatalogReleasesError(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCatalogReleases([])
          setCatalogReleasesError(true)
        }
      })

    if (currentUserId) {
      api
        .getArtistFollowStatus(artistId)
        .then((res) => {
          if (!cancelled) setFollowing(res.following)
        })
        .catch(() => {
          if (!cancelled) setFollowing(false)
        })
    }

    api
      .getArtistListeners(artistId)
      .then((res) => {
        if (!cancelled) setListeners(res)
      })
      .catch(() => {})

    return () => {
      cancelled = true
      if (supplementalPollRef.current) clearTimeout(supplementalPollRef.current)
    }
  }, [artistId])

  useEffect(() => {
    const row = similarRowRef.current
    if (!row) return
    const update = () => {
      const maxScroll = Math.max(0, row.scrollWidth - row.clientWidth)
      setSimilarCanPrev(row.scrollLeft > 2)
      setSimilarCanNext(row.scrollLeft < maxScroll - 2)
    }
    update()
    row.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      row.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [similarArtists, artistId])

  function startSupplementalPoll(
    id: number,
    attempts: number,
    isCancelled: () => boolean,
  ) {
    if (attempts >= 20) return
    supplementalPollRef.current = setTimeout(async () => {
      if (isCancelled()) return
      try {
        const data = await api.getArtistSupplemental(id)
        if (!isCancelled()) {
          setSupplemental(data)
          if (data.status === 'fetching' || data.status === 'pending') {
            startSupplementalPoll(id, attempts + 1, isCancelled)
          }
        }
      } catch { }
    }, 3000)
  }

  const handleFollow = async () => {
    if (followLoading) return
    const prevFollowing = following
    const prevFollowerCount = artist?.follower_count
    const willFollow = !(prevFollowing === true)
    setFollowing(willFollow)
    setArtist((prev) =>
      prev
        ? {
            ...prev,
            follower_count: Math.max(
              0,
              (prev.follower_count ?? 0) + (willFollow ? 1 : -1),
            ),
          }
        : prev,
    )
    haptic('light')
    setFollowLoading(true)
    try {
      const res = await api.toggleArtistFollow(artistId)
      setFollowing(res.following)
      setArtist((prev) =>
        prev
          ? { ...prev, follower_count: res.follower_count }
          : prev,
      )
    } catch (e) {
      if (_isNetworkError(e)) {
        await queueMutation(
          'POST',
          `/api/v1/artists/${artistId}/follow`,
        )
        setFollowLoading(false)
        return
      }
      setFollowing(prevFollowing)
      setArtist((prev) =>
        prev && prevFollowerCount != null
          ? { ...prev, follower_count: prevFollowerCount }
          : prev,
      )
      hapticNotification('error')
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(
          e,
          t('artist.follow_failed', 'Не удалось обновить подписку'),
        ),
        durationMs: 4000,
      })
    }
    setFollowLoading(false)
  }

  const handleEnrich = async () => {
    setEnriching(true)
    setEnrichError(null)
    try {
      const updated =
        await api.enrichArtist(artistId)
      setArtist(updated)
    } catch {
      setEnrichError(t('artist.enrich_failed'))
    } finally {
      setEnriching(false)
    }
  }

  const handleEnrichWatch = async () => {
    setDebugRunning(true)
    setDebugStage('queued')
    setDebugLogs([])
    setDebugTaskId(null)
    setDebugOpen(true)
    setEnrichError(null)
    let taskId = ''
    try {
      const res = await api.enrichArtistWatch(artistId)
      taskId = res.task_id
      setDebugTaskId(taskId)
    } catch {
      setDebugRunning(false)
      setDebugStage('error')
      setEnrichError(t('artist.enrich_failed'))
      return
    }
    const terminal = new Set([
      'done',
      'not_found',
      'error',
    ])
    while (true) {
      await new Promise((r) => setTimeout(r, 1000))
      let status
      try {
        status = await api.getArtistEnrichStatus(
          artistId,
          taskId,
        )
      } catch {
        continue
      }
      setDebugStage(status.stage ?? null)
      setDebugLogs(status.logs ?? [])
      if (
        status.stage &&
        terminal.has(status.stage)
      ) {
        break
      }
      if (status.status !== 'pending') break
    }
    try {
      const updated = await api.getArtist(artistId)
      setArtist(updated)
    } catch {
      /* ignore refresh failures */
    }
    setDebugRunning(false)
  }

  const profiles = useMemo<ArtistSourceProfile[]>(
    () =>
      artist?.source_profiles?.filter(
        (p): p is ArtistSourceProfile =>
          Boolean(p && p.source_id && p.source_name),
      ) ?? [],
    [artist],
  )

  const view = useMemo<ArtistViewData | null>(() => {
    if (!artist) return null
    const platformView = buildPlatformSupplementalView(artist, supplemental)
    if (selectedSourceId === 'platform' && platformView) return platformView
    // if (selectedSourceId === 'yandex') {
    //   return {
    //     source_id: 'yandex',
    //     source_name: t('artistSupplemental.tabLabel', { defaultValue: 'Яндекс' }),
    //     source_page_url: null,
    //     bio: supplemental?.content ?? null,
    //     birth_date: null,
    //     birthplace: null,
    //     country: null,
    //     image_url: artist.image_url,
    //     website_url: null,
    //     discography: [],
    //   }
    // }
    if (selectedSourceId) {
      const found = profiles.find(
        (p) => p.source_id === selectedSourceId,
      )
      if (found) {
        return buildProfileView(found, artist.image_url)
      }
    }
    if (platformView) return platformView
    return buildMergedView(artist)
  }, [artist, profiles, selectedSourceId, supplemental])

  const primaryProfile = useMemo<
    ArtistSourceProfile | null
  >(() => {
    if (!profiles.length) return null
    if (artist?.primary_source_id) {
      const exact = profiles.find(
        (p) => p.source_id === artist.primary_source_id,
      )
      if (exact) return exact
    }
    return profiles[0]
  }, [artist?.primary_source_id, profiles])

  if (!artist || !view) {
    return (
      <div className="author-view">
        <div className="author-view-header">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="author-back-btn icon-btn"
            onClick={onClose}
          >
            <Icon name="chevron" size={18} />
            {t('common.back', {
              defaultValue: 'Назад',
            })}
          </MotionPress>
        </div>
        <div className="author-hero">
          <div className="profile-avatar skeleton" />
          <div
            className="skeleton"
            style={{
              width: 160,
              height: 20,
              borderRadius: 6,
              marginTop: 12,
            }}
          />
        </div>
      </div>
    )
  }

  if (selectedReleaseId !== null) {
    return (
      <ArtistCatalogReleasePanel
        artistId={artistId}
        releaseId={selectedReleaseId}
        artistName={artist.name}
        onBack={() => setSelectedReleaseId(null)}
      />
    )
  }

  const computedAge =
    selectedSourceId === null
      ? artist.age
      : view.birth_date
        ? computeAge(view.birth_date)
        : null

  const metaParts: string[] = []
  if (computedAge !== null && computedAge !== undefined) {
    metaParts.push(t('artist.age', { count: computedAge }))
  }
  const cleanBirthplace = cleanWikiText(view.birthplace)
  if (cleanBirthplace) {
    metaParts.push(cleanBirthplace)
  } else if (view.country) {
    metaParts.push(view.country)
  }
  if (metaParts.length === 0) {
    metaParts.push(t('artist.performer'))
  }
  const infoKnown = hasAnyInfo(view)
  const showPending =
    !infoKnown &&
    (artist.enrichment_status === 'pending' ||
      artist.enrichment_status === 'in_progress')
  const showNoInfo =
    !infoKnown &&
    !showPending &&
    (artist.enrichment_status === 'done' ||
      artist.enrichment_status === 'not_found' ||
      artist.enrichment_status === 'failed')

  const progressPct =
    stageProgress[debugStage ?? ''] ?? 5
  const avatarSrc = view.image_url || artist.image_url
  const avatarCoverKey =
    !avatarSrc && artist.image_key ? artist.image_key : null
  const avatarViewerSrc =
    avatarSrc ||
    (avatarCoverKey
      ? coverProxyUrl(avatarCoverKey, { width: 480 })
      : null)
  const sourceName =
    view.source_name ??
    primaryProfile?.source_name ??
    null
  const sourcePageUrl =
    view.source_page_url ??
    primaryProfile?.source_page_url ??
    null
  const monthlyListenersValue =
    listeners?.current_month_listeners ??
    artist.monthly_listeners ??
    0

  return (
    <div className="author-view">
      <div className="author-view-header">
        <MotionPress
          type="button"
          variant="ghost"
          haptic="light"
          className="author-back-btn icon-btn"
          onClick={onClose}
        >
          <Icon name="chevron" size={18} />
          {t('common.back', {
            defaultValue: 'Назад',
          })}
        </MotionPress>
      </div>

      <div className="author-hero">
        {avatarCoverKey ? (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="artist-avatar-button"
            ariaLabel={t('artist.avatar_open')}
            onClick={() => setAvatarOpen(true)}
          >
            <div className="profile-avatar profile-avatar--cover">
              <CoverImage coverKey={avatarCoverKey} size={120} />
            </div>
          </MotionPress>
        ) : avatarSrc ? (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="artist-avatar-button"
            ariaLabel={t('artist.avatar_open')}
            onClick={() => setAvatarOpen(true)}
          >
            <div className="profile-avatar">
              <img src={avatarSrc} alt={artist.name} />
            </div>
          </MotionPress>
        ) : (
          <div className="profile-avatar">
            {artist.name.charAt(0).toUpperCase()}
          </div>
        )}
        <div className="author-name">
          {artist.name}
        </div>
        <p
          className="author-username"
          style={{ marginTop: 8 }}
        >
          {metaParts.join(' • ')}
        </p>

        <p className="artist-monthly-listeners-inline">
          <Icon name="users-listeners" size={14} />
          <span>
            {fmtCount(monthlyListenersValue)}{' '}
            {monthlyListenersText(monthlyListenersValue)}
          </span>
        </p>

        {/* Follow button (only for logged-in users) */}
        {currentUserId && (
          <MotionPress
            type="button"
            variant={following === true ? 'subtle' : 'primary'}
            haptic="medium"
            className={`artist-follow-btn${following === true ? ' artist-follow-btn--active' : ''}`}
            aria-pressed={following === true}
            onClick={handleFollow}
            disabled={followLoading}
          >
            <Icon
              name={following === true ? 'check' : 'bell'}
              size={14}
            />
            {followLoading
              ? '...'
              : following === true
                ? t('artist.following', {
                    defaultValue: 'Подписан',
                  })
                : t('artist.follow', {
                    defaultValue: 'Подписаться',
                  })}
          </MotionPress>
        )}

        {/* Listen Snippets Button */}
        {tracks && tracks.length > 0 && (
          <div className="rf-artist-snippet-wrap">
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary rf-artist-snippet-btn"
              onClick={toggleSnippet}
            >
              <MorphIcon
                name={snippetPlaying ? 'pause' : 'play'}
                size={16}
                filled
              />
              {snippetPlaying
                ? t(
                    'redesign.artist.stopPreview',
                    'Остановить превью',
                  )
                : t(
                    'redesign.artist.listenSnippets',
                    'Слушать их песни',
                  )}
            </MotionPress>
            <audio
              ref={audioRef}
              src={`/api/v1/track-preview/${tracks[snippetIndex].id}/segment.m4a`}
              onEnded={handleSnippetEnded}
              preload="none"
              className="rf-artist-snippet-audio"
            />
          </div>
        )}

        {(profiles.length > 0 || supplemental?.status === 'done') && (
          <div
            className="artist-source-switcher"
            role="tablist"
            aria-label={t('artist.sources_label')}
          >
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              role="tab"
              aria-selected={selectedSourceId === null}
              className={
                selectedSourceId === null
                  ? 'artist-source-chip active'
                  : 'artist-source-chip'
              }
              onClick={() => setSelectedSourceId(null)}
            >
              {t('artist.bio_title')}
            </MotionPress>
            {profiles.map((p) => (
              <MotionPress
                key={p.source_id}
                type="button"
                variant="ghost"
                haptic="selection"
                role="tab"
                aria-selected={selectedSourceId === p.source_id}
                className={
                  selectedSourceId === p.source_id
                    ? 'artist-source-chip active'
                    : 'artist-source-chip'
                }
                onClick={() => setSelectedSourceId(p.source_id)}
              >
                {p.source_name}
              </MotionPress>
            ))}
            {supplemental && supplemental.status === 'done' && (
              <MotionPress
                type="button"
                variant="ghost"
                haptic="selection"
                role="tab"
                aria-selected={selectedSourceId === 'platform'}
                className={
                  selectedSourceId === 'platform'
                    ? 'artist-source-chip active'
                    : 'artist-source-chip'
                }
                onClick={() => setSelectedSourceId('platform')}
              >
                {t(
                  'redesign.artist.sourcePlatform',
                  'Платформа',
                )}
              </MotionPress>
            )}
            {/* {supplemental && (supplemental.status === 'done' || supplemental.status === 'fetching' || supplemental.status === 'pending') && (
              <button
                type="button"
                role="tab"
                aria-selected={selectedSourceId === 'yandex'}
                className={
                  selectedSourceId === 'yandex'
                    ? 'artist-source-chip active'
                    : 'artist-source-chip'
                }
                onClick={() => supplemental.status === 'done' ? setSelectedSourceId('yandex') : undefined}
                disabled={supplemental.status !== 'done'}
                title={supplemental.status !== 'done' ? t('artistSupplemental.loading', { defaultValue: 'Загрузка...' }) : undefined}
              >
                {supplemental.status === 'done'
                  ? t('artistSupplemental.tabLabel', { defaultValue: 'Яндекс' })
                  : t('artistSupplemental.loading', { defaultValue: 'Яндекс…' })}
              </button>
            )} */}
          </div>
        )}

        {sourceName && (
          <div className="artist-source-attribution">
            {t('artist.source_attribution')}:{' '}
            {sourcePageUrl ? (
              <a
                href={sourcePageUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {sourceName}
              </a>
            ) : (
              sourceName
            )}
          </div>
        )}

        {isAdmin && (
          <div
            className="artist-admin-actions"
            style={{ marginTop: 12 }}
          >
            <div className="artist-admin-row">
              <MotionPress
                type="button"
                variant="primary"
                haptic="medium"
                className="btn-primary artist-enrich-btn"
                onClick={handleEnrich}
                disabled={enriching || debugRunning}
              >
                {enriching
                  ? t('artist.enrich_loading')
                  : t('artist.enrich_button')}
              </MotionPress>
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="btn-secondary artist-enrich-btn"
                title={t('artist.debug_run')}
                onClick={handleEnrichWatch}
                disabled={enriching || debugRunning}
              >
                {debugRunning
                  ? t('artist.debug_running')
                  : t('artist.debug_run')}
              </MotionPress>
            </div>

            {enrichError && (
              <div
                className="form-error"
                style={{ marginTop: 6 }}
              >
                {enrichError}
              </div>
            )}

            {(debugRunning ||
              (debugLogs.length > 0 &&
                debugStage !== null)) && (
              <div style={{ marginTop: 10 }}>
                {/* Progress bar */}
                <div
                  style={{
                    width: '100%',
                    height: 3,
                    borderRadius: 2,
                    background:
                      'rgba(255,255,255,0.08)',
                    overflow: 'hidden',
                    marginBottom: 8,
                  }}
                >
                  <div
                    style={{
                      width: `${progressPct}%`,
                      height: '100%',
                      borderRadius: 2,
                      background:
                        'rgba(255,255,255,0.5)',
                      transition:
                        'width 0.6s ease-in-out',
                    }}
                  />
                </div>

                {/* Stage + elapsed + gear toggle */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 12,
                    color: 'rgba(255,255,255,0.5)',
                  }}
                >
                  <span>
                    {debugRunning
                      ? t(
                          'artist.enrich_loading',
                          'Обогащение...',
                        )
                      : debugStage ?? ''}
                  </span>
                  {debugRunning && (
                    <span
                      style={{
                        fontSize: 11,
                        color: 'rgba(255,255,255,0.3)',
                      }}
                    >
                      {elapsed}s
                    </span>
                  )}
                  <button
                    onClick={() =>
                      setDebugOpen((v) => !v)
                    }
                    style={{
                      marginLeft: 'auto',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 2,
                      display: 'flex',
                      alignItems: 'center',
                      color: 'rgba(255,255,255,0.7)',
                    }}
                    title={t('artist.debug_toggle')}
                    aria-label={t(
                      'artist.debug_toggle',
                    )}
                  >
                    <Icon name="settings" size={16} />
                  </button>
                </div>

                {/* DevTools panel */}
                {debugOpen && (
                  <div
                    style={{
                      background:
                        'rgba(10,10,10,0.95)',
                      border:
                        '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 10,
                      padding: '8px 10px',
                      fontSize: 10,
                      fontFamily: 'monospace',
                      color: 'rgba(255,255,255,0.7)',
                      maxHeight: '40vh',
                      overflow: 'auto',
                      marginTop: 8,
                      backdropFilter: 'blur(8px)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        marginBottom: 6,
                        flexWrap: 'wrap',
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 700,
                          color: '#fff',
                          fontSize: 11,
                        }}
                      >
                        DevTools — Artist
                      </span>
                      <span
                        style={{
                          padding: '1px 5px',
                          borderRadius: 4,
                          fontSize: 9,
                          background: debugRunning
                            ? 'rgba(250,204,21,0.2)'
                            : 'rgba(74,222,128,0.2)',
                          color: debugRunning
                            ? '#facc15'
                            : '#4ade80',
                        }}
                      >
                        {debugRunning
                          ? 'RUNNING'
                          : 'DONE'}
                      </span>
                      <button
                        onClick={() =>
                          setDebugLogs([])
                        }
                        style={{
                          marginLeft: 'auto',
                          background:
                            'rgba(255,255,255,0.08)',
                          border: 'none',
                          color:
                            'rgba(255,255,255,0.5)',
                          borderRadius: 4,
                          padding: '2px 6px',
                          fontSize: 9,
                          cursor: 'pointer',
                        }}
                      >
                        Clear
                      </button>
                      <button
                        onClick={() =>
                          setDebugOpen(false)
                        }
                        style={{
                          background:
                            'rgba(255,255,255,0.08)',
                          border: 'none',
                          color:
                            'rgba(255,255,255,0.5)',
                          borderRadius: 4,
                          padding: '2px 6px',
                          fontSize: 9,
                          cursor: 'pointer',
                        }}
                      >
                        Close
                      </button>
                    </div>
                    <div
                      style={{
                        color: 'rgba(255,255,255,0.4)',
                        fontSize: 9,
                        marginBottom: 4,
                      }}
                    >
                      task: {debugTaskId ?? '-'}
                      {' | '}
                      elapsed: {elapsed}s
                      {' | '}
                      stage: {debugStage ?? '-'}
                    </div>
                    <div
                      style={{
                        borderTop:
                          '1px solid rgba(255,255,255,0.08)',
                        paddingTop: 4,
                      }}
                    >
                      {debugLogs.length === 0 ? (
                        <div
                          style={{
                            color:
                              'rgba(255,255,255,0.3)',
                          }}
                        >
                          {t('artist.debug_empty')}
                        </div>
                      ) : (
                        debugLogs.map((line, i) => (
                          <div
                            key={i}
                            style={{
                              padding: '1px 0',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                            }}
                          >
                            {line}
                          </div>
                        ))
                      )}
                      <div ref={logEndRef} />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {view.bio && (
        <div className="artist-bio-section">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="section-header artist-bio-toggle"
            onClick={() => setBioOpen((v) => !v)}
          >
            <span className="section-title">
              {t('artist.bio_title')}
            </span>
            <span className="artist-bio-chevron">
              <Icon name="chevron" size={14} />
            </span>
          </MotionPress>
          <div
            className={
              bioOpen
                ? 'artist-bio-text'
                : 'artist-bio-text artist-bio-collapsed'
            }
          >
            {view.bio}
          </div>
          {!bioOpen && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="artist-bio-more"
              onClick={() => setBioOpen(true)}
            >
              {t('artist.bio_show_more')}
            </MotionPress>
          )}
          {bioOpen && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="artist-bio-more"
              onClick={() => setBioOpen(false)}
            >
              {t('artist.bio_show_less')}
            </MotionPress>
          )}
        </div>
      )}

      {(view.birth_date ||
        cleanBirthplace ||
        view.website_url) && (
        <div className="artist-meta-row">
          {view.birth_date && (
            <span>
              {t('artist.born')}: {view.birth_date}
            </span>
          )}
          {cleanBirthplace && (
            <span>
              {t('artist.birthplace')}:{' '}
              {cleanBirthplace}
            </span>
          )}
          {view.website_url && (
            <a
              href={view.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="artist-website-link"
            >
              {t('artist.website')}
            </a>
          )}
        </div>
      )}

      {showPending && (
        <div className="artist-empty-info">
          {t('artist.enrichment_pending')}
        </div>
      )}

      {showNoInfo && (
        <div className="artist-empty-info">
          {t('artist.no_info')}
        </div>
      )}

      {catalogReleases !== null && (
        <div className="artist-catalog-releases">
          <div className="section-header">
            <span className="section-title">
              {t('artist.catalog_releases_title')}{' '}
              ({catalogReleases.length})
            </span>
          </div>
          {catalogReleasesError && (
            <div className="artist-empty-info">
              {t('artist.catalog_releases_load_error')}
            </div>
          )}
          {!catalogReleasesError &&
            catalogReleases.length === 0 && (
              <div className="artist-empty-info">
                {isAdmin
                  ? t('artist.catalog_releases_empty_admin')
                  : t('artist.catalog_releases_empty')}
              </div>
            )}
          {!catalogReleasesError &&
            catalogReleases.length > 0 && (
              <div className="artist-catalog-releases-grid">
                {catalogReleases.map((r) => {
                  const y = r.released_at?.match(
                    /^(\d{4})/,
                  )?.[1]
                  const metaBits: string[] = []
                  if (y) metaBits.push(y)
                  metaBits.push(
                    t('artist.catalog_release_card_tracks', {
                      count: r.track_count,
                    }),
                  )
                  const isScStation =
                    r.release_kind === 'dotsound_sc_artist_station'
                  return (
                    <MotionPress
                      key={r.id}
                      type="button"
                      variant="subtle"
                      haptic="light"
                      className={
                        isScStation
                          ? 'artist-catalog-release-card artist-catalog-release-card-station'
                          : 'artist-catalog-release-card'
                      }
                      onClick={() => {
                        setAvatarOpen(false)
                        setSelectedReleaseId(r.id)
                      }}
                    >
                      <CoverImage coverKey={r.cover_key} size={56} />
                      <div className="artist-catalog-release-card-text">
                        <div className="artist-catalog-release-card-title">
                          {r.title}
                        </div>
                        <div className="artist-catalog-release-card-meta">
                          {metaBits.join(' · ')}
                        </div>
                        {isScStation && (
                          <span className="artist-catalog-release-station-badge">
                            {t('artist.catalog_release_station_badge')}
                          </span>
                        )}
                      </div>
                    </MotionPress>
                  )
                })}
              </div>
            )}
        </div>
      )}

      {view.discography.length > 0 && (
        <div className="artist-discography">
          <div className="section-header">
            <span className="section-title">
              {t('artist.discography_title')}{' '}
              ({view.discography.length})
            </span>
          </div>
          {view.discography.map((item, i) => (
            <div
              key={`${item.title}-${i}`}
              className="discography-item"
            >
              {item.url ? (
                <a
                  className="discography-title"
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {item.title}
                </a>
              ) : (
                <span className="discography-title">
                  {item.title}
                </span>
              )}
              {item.year && (
                <span className="discography-year">
                  {item.year}
                </span>
              )}
              {item.type && (
                <span className="discography-type">
                  {item.type}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Admin: refresh Yandex supplemental (temporarily disabled) */}
      {/* {isAdmin && supplemental?.status === 'done' && (
        <div style={{ padding: '0 16px 8px' }}>
          <button
            className="btn-secondary artist-supplemental-refresh"
            onClick={handleRefreshSupplemental}
            disabled={refreshingSupplemental}
          >
            <Icon name="refresh" size={13} />
            {refreshingSupplemental
              ? t('trackInfo.loading', { defaultValue: 'Обновление...' })
              : t('trackInfo.refresh', { defaultValue: 'Обновить Яндекс' })}
          </button>
        </div>
      )} */}

      {similarArtists &&
        similarArtists.length > 0 &&
        onSelectSimilarArtist && (
        <div className="artist-similar-section">
          <div className="section-header">
            <span className="section-title">
              {t('artist.similar_title', {
                defaultValue: 'Похожие',
              })}
            </span>
          </div>
          <div className="artist-similar-shell">
            {similarCanPrev && (
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="artist-similar-arrow artist-similar-arrow--left"
                ariaLabel={t('common.prev', {
                  defaultValue: 'Назад',
                })}
                onClick={() =>
                  similarRowRef.current?.scrollBy({
                    left: -220,
                    behavior: 'smooth',
                  })
                }
              >
                <Icon
                  name="chevron"
                  size={18}
                  className="artist-similar-arrow__icon artist-similar-arrow__icon--left"
                />
              </MotionPress>
            )}
            <div
              ref={similarRowRef}
              className="artist-similar-row"
            >
              {similarArtists.map((a) => {
                const imageSrc = artistImageUrl(a.image_key)
                return (
                  <MotionPress
                    key={a.id}
                    type="button"
                    variant="subtle"
                    haptic="light"
                    className="artist-similar-card"
                    onClick={() =>
                      onSelectSimilarArtist(a.id)
                    }
                  >
                    <div className="artist-similar-card__avatar">
                      {imageSrc ? (
                        <img
                          src={imageSrc}
                          alt=""
                          loading="lazy"
                          decoding="async"
                        />
                      ) : (
                        <div className="artist-similar-card__avatar-placeholder">
                          <Icon name="user" size={20} />
                        </div>
                      )}
                    </div>
                    <span className="artist-similar-card__name">
                      {a.name}
                    </span>
                  </MotionPress>
                )
              })}
            </div>
            {similarCanNext && (
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="artist-similar-arrow artist-similar-arrow--right"
                ariaLabel={t('common.next', {
                  defaultValue: 'Вперёд',
                })}
                onClick={() =>
                  similarRowRef.current?.scrollBy({
                    left: 220,
                    behavior: 'smooth',
                  })
                }
              >
                <Icon name="chevron" size={18} />
              </MotionPress>
            )}
          </div>
        </div>
      )}

      {/* Monthly listeners history */}
      {listeners && listeners.history.length > 0 && (
        <div className="artist-listeners-section">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="section-header artist-bio-toggle"
            onClick={() =>
              setListenersOpen((v) => !v)
            }
          >
            <span className="section-title">
              {t('artist.listeners_history_title', {
                defaultValue: 'Статистика слушателей',
              })}
            </span>
            <span className="artist-bio-chevron">
              <Icon name="chevron" size={14} />
            </span>
          </MotionPress>
          {listenersOpen && (
            <>
              <ArtistListenersChart
                history={listeners.history}
              />
              <Link
                to={`/artist/${artistId}/stats`}
                className="artist-more-stats-link"
                onClick={() => onClose()}
              >
                {t('artistStats.title', { name: '', defaultValue: 'Подробная статистика' })}
                <Icon name="chevron-right" size={14} />
              </Link>
            </>
          )}
        </div>
      )}

      {/* Platform tracks */}
      <div className="section-header">
        <span className="section-title">
          {t('artist.tracks_title')}{' '}
          {tracks !== null && tracks.length > 0
            ? `(${tracks.length})`
            : ''}
        </span>
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage={t('artist.tracks_empty')}
      />

      {avatarOpen && avatarViewerSrc && (
        <ArtistAvatarViewer
          src={avatarViewerSrc}
          alt={artist.name}
          onClose={() => setAvatarOpen(false)}
        />
      )}
    </div>
  )
}
