import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'

import '@/styles/redesign-artist.css'

import { api, getApiErrorMessage } from '@/lib/api'
import { coverProxyUrl } from '@/lib/coverProxy'
import { useAutoLoadMore } from '@/hooks/useAutoLoadMore'
import { VARIANTS_FADE_UP, m } from '@/lib/motion'
import { setBackButton } from '@/lib/telegram'

import {
  usePlayerActions,
} from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'

import type { AlbumWithTracksRecord, Track } from '@/types/api'

const ALBUM_TRACKS_PAGE_SIZE = 30

function albumCoverUrl(
  key: string | null | undefined,
): string | null {
  if (!key) return null
  return coverProxyUrl(key, { width: 480 })
}

function openExternalLink(url: string) {
  try {
    const tg = (
      window as unknown as {
        Telegram?: {
          WebApp?: {
            openLink?: (u: string) => void
          }
        }
      }
    ).Telegram?.WebApp
    if (tg?.openLink) {
      tg.openLink(url)
      return
    }
  } catch {
    /* ignore */
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

function detectExternalSource(
  tracks: Track[] | null | undefined,
): { name: string | null; url: string | null } {
  if (!tracks || tracks.length === 0) {
    return { name: null, url: null }
  }
  for (const t of tracks) {
    if (t.source_name && (t.source_url || t.canonical_source_url)) {
      return {
        name: t.source_name,
        url: t.source_url ?? t.canonical_source_url,
      }
    }
  }
  return { name: null, url: null }
}

export function ExternalAlbumView() {
  const { id: idParam } = useParams<{ id: string }>()
  const albumId = Number(idParam)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { playTrack } = usePlayerActions()

  const [album, setAlbum] =
    useState<AlbumWithTracksRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tracksLoadingMore, setTracksLoadingMore] = useState(false)
  const tracksCursorRef = useRef<string | null>(null)

  const goBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate('/')
    }
  }, [navigate])

  useEffect(() => {
    setBackButton(true, goBack)
    return () => {
      setBackButton(false)
    }
  }, [goBack])

  useEffect(() => {
    if (!Number.isFinite(albumId)) return
    let cancelled = false
    tracksCursorRef.current = null
    setAlbum(null)
    setError(null)
    api
      .getAlbum(albumId, {
        tracksPage: 1,
        tracksSize: ALBUM_TRACKS_PAGE_SIZE,
      })
      .then((d) => {
        if (cancelled) return
        tracksCursorRef.current = d.tracks_next_cursor ?? null
        setAlbum(d)
      })
      .catch((e) => {
        if (cancelled) return
        setError(
          getApiErrorMessage(e, t('redesign.artist.loadError')),
        )
      })
    return () => {
      cancelled = true
    }
  }, [albumId, t])

  const tracks = album?.tracks ?? null
  const tracksHasMore = Boolean(album?.tracks_has_more)
  usePrefetchTracks(tracks, 'album')

  const heroUrl = useMemo(
    () => albumCoverUrl(album?.cover_key),
    [album?.cover_key],
  )

  const sourceInfo = useMemo(
    () => detectExternalSource(tracks),
    [tracks],
  )

  const handlePlayAll = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      await playTrack(tracks[0], { contextTracks: tracks })
    } catch (e) {
      showIsland({ kind: 'error', title: getApiErrorMessage(e, t('redesign.artist.playError')), durationMs: 4000 })
    }
  }, [tracks, playTrack, t])

  const handleOpenSource = useCallback(() => {
    if (!sourceInfo.url) return
    openExternalLink(sourceInfo.url)
  }, [sourceInfo.url])

  const loadMoreTracks = useCallback(async () => {
    if (!Number.isFinite(albumId) || tracksLoadingMore || !tracksHasMore) {
      return
    }
    setTracksLoadingMore(true)
    try {
      const cursor =
        album?.tracks_next_cursor ?? tracksCursorRef.current
      if (!cursor) return
      const next = await api.getAlbum(albumId, {
        tracksSize: ALBUM_TRACKS_PAGE_SIZE,
        tracksCursor: cursor,
      })
      tracksCursorRef.current = next.tracks_next_cursor ?? null
      setAlbum((prev) =>
        prev
          ? {
              ...prev,
              tracks: [...prev.tracks, ...next.tracks],
              tracks_total: next.tracks_total,
              tracks_page: next.tracks_page,
              tracks_size: next.tracks_size,
              tracks_has_more: next.tracks_has_more,
              tracks_next_cursor: next.tracks_next_cursor,
            }
          : next,
      )
    } catch (e) {
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(e, t('redesign.artist.loadError')),
        durationMs: 3500,
      })
    } finally {
      setTracksLoadingMore(false)
    }
  }, [album?.tracks_next_cursor, albumId, tracksHasMore, tracksLoadingMore, t])

  const tracksSentinelRef = useAutoLoadMore({
    enabled: tracksHasMore,
    loading: tracksLoadingMore,
    onLoadMore: loadMoreTracks,
  })

  if (!Number.isFinite(albumId)) {
    return (
      <section className="view active rf-external">
        <div className="rf-artist__error">
          {t('redesign.artist.invalidId')}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="view active rf-external">
        <header className="rf-external__chrome">
          <MotionPress
            variant="icon"
            haptic="light"
            ariaLabel={t('redesign.artist.backAria')}
            onClick={goBack}
          >
            <Icon name="chevron" size={20} className="back-chevron" />
          </MotionPress>
        </header>
        <div className="rf-artist__error">{error}</div>
      </section>
    )
  }

  return (
    <section className="view active rf-external">
      <header className="rf-external__chrome">
        <MotionPress
          variant="icon"
          haptic="light"
          ariaLabel={t('redesign.artist.backAria')}
          onClick={goBack}
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </MotionPress>
        <span
          className="rf-artist__chrome-title"
          aria-hidden="true"
        >
          {album?.title ?? ''}
        </span>
      </header>

      <AmbientStage
        coverUrl={heroUrl}
        className="rf-external__hero"
      >
        <div className="rf-external__hero-inner">
          <div className="rf-external__hero-art">
            {heroUrl ? (
              <KenBurnsCover src={heroUrl} alt="" />
            ) : (
              <Icon name="music" size={48} />
            )}
          </div>
          <span className="rf-external__badge">
            <Icon name="link-external" size={12} />
            {t('redesign.artist.badgeExternal')}
          </span>
          <h1 className="rf-external__title">
            {album?.title ?? ' '}
          </h1>
          {album?.description && (
            <p className="rf-external__artist">
              {album.description}
            </p>
          )}
          <div className="rf-external__actions">
            <MotionPress
              variant="primary"
              haptic="medium"
              onClick={() => {
                void handlePlayAll()
              }}
              disabled={!tracks || tracks.length === 0}
            >
              <Icon name="play" size={16} />
              <span>{t('redesign.artist.play')}</span>
            </MotionPress>
            {sourceInfo.name && sourceInfo.url && (
              <MotionPress
                variant="ghost"
                haptic="light"
                onClick={handleOpenSource}
                className="rf-external__source-btn"
              >
                <Icon name="link-external" size={14} />
                <span>{sourceInfo.name}</span>
              </MotionPress>
            )}
          </div>
        </div>
      </AmbientStage>

      <m.div
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
      >
        <TrackList
          tracks={tracks}
          emptyMessage={t('redesign.artist.noTracks')}
        />
        {tracksHasMore && (
          <>
            <div ref={tracksSentinelRef} aria-hidden />
            <MotionPress
              variant="ghost"
              haptic="light"
              className="rd-liked-more"
              onClick={() => {
                void loadMoreTracks()
              }}
              disabled={tracksLoadingMore}
            >
              {tracksLoadingMore
                ? t('common.loading')
                : t('common.showMore')}
            </MotionPress>
          </>
        )}
      </m.div>
    </section>
  )
}
