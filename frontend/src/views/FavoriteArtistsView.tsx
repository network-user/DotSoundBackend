import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { MotionPress } from '@/components/ui/MotionPress'
import { useAutoLoadMore } from '@/hooks/useAutoLoadMore'
import { api, getApiErrorMessage } from '@/lib/api'
import { coverProxyUrl } from '@/lib/coverProxy'
import { showIsland } from '@/lib/island'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { usePlayerActions } from '@/store/PlayerContext'
import type { FollowedArtistItem, Track } from '@/types/api'

interface FavoriteArtistsViewProps {
  embedded?: boolean
}

type ArtistSelection = 'all' | number

const PAGE_SIZE = 30

function artistImageUrl(artist: FollowedArtistItem): string | null {
  return artist.image_key
    ? coverProxyUrl(artist.image_key, { width: 120 })
    : null
}

export function FavoriteArtistsView({
  embedded = false,
}: FavoriteArtistsViewProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { playTrack } = usePlayerActions()
  const [artists, setArtists] = useState<
    FollowedArtistItem[] | null
  >(null)
  const [selectedArtistId, setSelectedArtistId] =
    useState<ArtistSelection>('all')
  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const pageRef = useRef(1)

  useEffect(() => {
    let cancelled = false
    api
      .getFollowedArtistsList(100)
      .then((data) => {
        if (!cancelled) setArtists(data.items)
      })
      .catch(() => {
        if (!cancelled) setArtists([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const selectedArtist = useMemo(() => {
    if (selectedArtistId === 'all') return null
    return (
      artists?.find((artist) => artist.id === selectedArtistId) ??
      null
    )
  }, [artists, selectedArtistId])

  const fetchTracks = useCallback(
    async (
      page: number,
      selection: ArtistSelection,
      reset: boolean,
    ) => {
      if (reset) {
        setTracks(null)
        setHasMore(false)
      }
      setLoading(true)
      try {
        const data =
          selection === 'all'
            ? await api.getFollowedArtistsTracks(
                page,
                PAGE_SIZE,
                true,
              )
            : await api.getArtistTracks(selection, page, PAGE_SIZE)
        setTracks((prev) =>
          reset || !prev
            ? data.items
            : [...prev, ...data.items],
        )
        setHasMore(
          data.has_more ?? data.total > page * PAGE_SIZE,
        )
        pageRef.current = page
      } catch {
        if (reset) setTracks([])
        setHasMore(false)
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    pageRef.current = 1
    void fetchTracks(1, selectedArtistId, true)
  }, [fetchTracks, selectedArtistId])

  usePrefetchTracks(tracks ?? null, 'library')

  const loadMore = useCallback(() => {
    if (loading || !hasMore) return
    void fetchTracks(
      pageRef.current + 1,
      selectedArtistId,
      false,
    )
  }, [fetchTracks, hasMore, loading, selectedArtistId])

  const sentinelRef = useAutoLoadMore({
    enabled: hasMore,
    loading,
    onLoadMore: loadMore,
  })

  const handlePlayAll = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      await playTrack(tracks[0], { contextTracks: tracks })
    } catch (err) {
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(
          err,
          t('favoriteArtists.playError'),
        ),
        durationMs: 4000,
      })
    }
  }, [playTrack, t, tracks])

  const tracksTitle = selectedArtist
    ? selectedArtist.name
    : t('favoriteArtists.allTracks')
  const loadedLabel =
    tracks && tracks.length > 0
      ? t('favoriteArtists.loaded', { count: tracks.length })
      : null

  const artistStrip =
    artists === null ? (
      <div className="rd-fav-artists__strip-skeleton">
        {[0, 1, 2, 3].map((item) => (
          <span key={item} className="rd-fav-artist-skel" />
        ))}
      </div>
    ) : artists.length > 0 ? (
      <div
        className="rd-fav-artists__strip"
        role="tablist"
        aria-label={t('favoriteArtists.filterAria')}
      >
        <MotionPress
          variant="subtle"
          haptic="selection"
          className="rd-fav-artist-chip rd-fav-artist-chip--all"
          data-active={
            selectedArtistId === 'all' ? 'true' : 'false'
          }
          role="tab"
          aria-selected={selectedArtistId === 'all'}
          onClick={() => setSelectedArtistId('all')}
        >
          <span className="rd-fav-artist-chip__avatar">
            <Icon name="users-following" size={18} />
          </span>
          <span className="rd-fav-artist-chip__name">
            {t('favoriteArtists.allArtists')}
          </span>
        </MotionPress>
        {artists.map((artist) => {
          const src = artistImageUrl(artist)
          return (
            <MotionPress
              key={artist.id}
              variant="subtle"
              haptic="selection"
              className="rd-fav-artist-chip"
              data-active={
                selectedArtistId === artist.id ? 'true' : 'false'
              }
              role="tab"
              aria-selected={selectedArtistId === artist.id}
              onClick={() => setSelectedArtistId(artist.id)}
            >
              <span className="rd-fav-artist-chip__avatar">
                {src ? (
                  <img src={src} alt="" loading="lazy" />
                ) : (
                  <Icon name="user" size={18} />
                )}
              </span>
              <span className="rd-fav-artist-chip__name">
                {artist.name}
              </span>
            </MotionPress>
          )
        })}
      </div>
    ) : (
      <div className="rd-fav-artists__empty">
        <span className="rd-fav-artists__empty-icon">
          <Icon name="users-following" size={24} />
        </span>
        <p>{t('favoriteArtists.emptyArtists')}</p>
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="rd-fav-artists__empty-action"
          onClick={() => navigate('/search?tab=artists')}
        >
          {t('favoriteArtists.findArtists')}
        </MotionPress>
      </div>
    )

  const list = (
    <>
      <div className="rd-fav-artists__top">
        <div className="rd-fav-artists__title-row">
          <div className="rd-fav-artists__title-block">
            <h2 className="rd-fav-artists__title">
              {tracksTitle}
            </h2>
            {loadedLabel && (
              <p className="rd-fav-artists__meta">
                {loadedLabel}
              </p>
            )}
          </div>
          <div className="rd-fav-artists__actions">
            {selectedArtist && (
              <MotionPress
                variant="icon"
                haptic="selection"
                className="rd-fav-artists__icon-action"
                ariaLabel={t('favoriteArtists.openArtist', {
                  name: selectedArtist.name,
                })}
                onClick={() => navigate(`/artist/${selectedArtist.id}`)}
              >
                <Icon name="chevron-right" size={18} />
              </MotionPress>
            )}
            {tracks && tracks.length > 0 && (
              <MotionPress
                variant="ghost"
                haptic="selection"
                className="rd-fav-artists__play"
                onClick={handlePlayAll}
              >
                <Icon name="play" size={14} />
                <span>{t('favoriteArtists.playAll')}</span>
              </MotionPress>
            )}
          </div>
        </div>
        {artistStrip}
      </div>
      {artists !== null && artists.length > 0 && (
        <>
          <TrackList
            tracks={tracks}
            emptyMessage={t('favoriteArtists.emptyTracks')}
            contextTracks={tracks ?? undefined}
          />
          {hasMore && (
            <>
              <div ref={sentinelRef} aria-hidden />
              <MotionPress
                variant="ghost"
                haptic="light"
                className="rd-liked-more"
                onClick={loadMore}
                disabled={loading}
              >
                {loading
                  ? t('favoriteArtists.loading')
                  : t('favoriteArtists.showMore')}
              </MotionPress>
            </>
          )}
        </>
      )}
    </>
  )

  if (embedded) {
    return (
      <div className="library-embed rd-fav-artists">{list}</div>
    )
  }

  return (
    <section
      id="view-favorite-artists"
      className="view active rd-fav-artists"
    >
      <div className="view-header rd-liked-header">
        <h2>{t('favoriteArtists.title')}</h2>
      </div>
      {list}
    </section>
  )
}

