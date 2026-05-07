import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { HorizontalSnap } from '@/components/ui/HorizontalSnap'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useToast } from '@/components/ui/Toast'

import { api, getApiErrorMessage } from '@/lib/api'
import { VARIANTS_FADE_UP, m } from '@/lib/motion'
import { hapticNotification, setBackButton } from '@/lib/telegram'

import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'

import type {
  ArtistDetail,
  ArtistInfo,
  Track,
} from '@/types/api'

function fmtCount(n: number | undefined | null): string {
  const v = Number(n ?? 0)
  if (!Number.isFinite(v) || v <= 0) return '0'
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(Math.round(v))
}

function artistImageUrl(
  detail: Pick<ArtistDetail, 'image_url' | 'image_key'> | null,
): string | null {
  if (!detail) return null
  if (detail.image_url) return detail.image_url
  if (detail.image_key) {
    return (
      '/api/v1/tracks/cover_proxy?key=' +
      encodeURIComponent(detail.image_key)
    )
  }
  return null
}

function similarImageUrl(item: ArtistInfo): string | null {
  if (item.image_key) {
    return (
      '/api/v1/tracks/cover_proxy?key=' +
      encodeURIComponent(item.image_key)
    )
  }
  return null
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

export function ArtistView() {
  const { id: idParam } = useParams<{ id: string }>()
  const artistId = Number(idParam)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const toast = useToast()

  const { playTrack, toggleShuffle } = usePlayerActions()
  const { shuffleOn } = usePlayerMeta()

  const [detail, setDetail] = useState<ArtistDetail | null>(null)
  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [similar, setSimilar] = useState<ArtistInfo[]>([])
  const [following, setFollowing] = useState<boolean>(false)
  const [followerCount, setFollowerCount] =
    useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [followBusy, setFollowBusy] = useState(false)

  const goBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate('/')
    }
  }, [navigate])

  useEffect(() => {
    setBackButton(true, goBack)
    return () => { setBackButton(false) }
  }, [goBack])

  useEffect(() => {
    if (!Number.isFinite(artistId)) return
    let cancelled = false

    setDetail(null)
    setTracks(null)
    setSimilar([])
    setError(null)

    api
      .getArtist(artistId)
      .then((d) => {
        if (cancelled) return
        setDetail(d)
        setFollowerCount(d.follower_count ?? 0)
      })
      .catch((e) => {
        if (cancelled) return
        setError(getApiErrorMessage(e, t('redesign.artist.loadError')))
      })

    api
      .getArtistTracks(artistId, 1)
      .then((res) => {
        if (cancelled) return
        setTracks(res.items ?? [])
      })
      .catch(() => {
        if (cancelled) return
        setTracks([])
      })

    api
      .getArtistFollowStatus(artistId)
      .then((s) => {
        if (cancelled) return
        setFollowing(Boolean(s.following))
      })
      .catch(() => {
        /* ignore */
      })

    api
      .listSimilarCatalogArtists(artistId, 12)
      .then((res) => {
        if (cancelled) return
        setSimilar(res.items ?? [])
      })
      .catch(() => {
        if (cancelled) return
        setSimilar([])
      })

    return () => {
      cancelled = true
    }
  }, [artistId, t])

  usePrefetchTracks(tracks, 'artist')

  const heroUrl = useMemo(() => artistImageUrl(detail), [detail])
  const sourceProfiles = detail?.source_profiles ?? []
  const primarySource =
    sourceProfiles.find(
      (p) => p.source_id === detail?.primary_source_id,
    ) ?? sourceProfiles[0] ?? null
  const sourceName = primarySource?.source_name ?? null
  const sourcePageUrl = primarySource?.source_page_url ?? null
  const externalWebsiteUrl = detail?.website_url ?? null

  const handlePlayAll = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      await playTrack(tracks[0])
    } catch (e) {
      toast.error(getApiErrorMessage(e, t('redesign.artist.playError')))
    }
  }, [tracks, playTrack, toast, t])

  const handleShuffle = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      if (!shuffleOn) toggleShuffle()
      const pick =
        tracks[Math.floor(Math.random() * tracks.length)]
      await playTrack(pick)
    } catch (e) {
      toast.error(getApiErrorMessage(e, t('redesign.artist.playError')))
    }
  }, [tracks, shuffleOn, toggleShuffle, playTrack, toast, t])

  const handleFollow = useCallback(async () => {
    if (!Number.isFinite(artistId) || followBusy) return
    setFollowBusy(true)
    try {
      const res = await api.toggleArtistFollow(artistId)
      setFollowing(res.following)
      setFollowerCount(res.follower_count)
      hapticNotification('success')
    } catch (e) {
      toast.error(
        getApiErrorMessage(e, t('redesign.artist.followError')),
      )
    } finally {
      setFollowBusy(false)
    }
  }, [artistId, followBusy, toast, t])

  const handleOpenSource = useCallback(() => {
    if (!sourcePageUrl) return
    openExternalLink(sourcePageUrl)
  }, [sourcePageUrl])

  const handleOpenExternalSite = useCallback(() => {
    if (!externalWebsiteUrl) return
    openExternalLink(externalWebsiteUrl)
  }, [externalWebsiteUrl])

  const handleOpenSimilar = useCallback(
    (id: number) => {
      navigate(`/artist/${id}`)
    },
    [navigate],
  )

  const handleOpenStats = useCallback(() => {
    navigate(`/artist/${artistId}/stats`)
  }, [navigate, artistId])

  if (!Number.isFinite(artistId)) {
    return (
      <section className="view active rf-artist">
        <div className="rf-artist__error">
          {t('redesign.artist.invalidId')}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="view active rf-artist">
        <header className="rf-artist__chrome">
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
    <section className="view active rf-artist">
      <header className="rf-artist__chrome" data-pinned="true">
        <MotionPress
          variant="icon"
          haptic="light"
          ariaLabel={t('redesign.artist.backAria')}
          onClick={goBack}
          className="rf-artist__chrome-btn"
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </MotionPress>
        <span
          className="rf-artist__chrome-title"
          aria-hidden="true"
        >
          {detail?.name ?? ''}
        </span>
        <MotionPress
          variant="icon"
          haptic="light"
          ariaLabel={t('redesign.artist.statsAria')}
          onClick={handleOpenStats}
          className="rf-artist__chrome-btn"
        >
          <Icon name="stats" size={18} />
        </MotionPress>
      </header>

      <AmbientStage
        coverUrl={heroUrl}
        className="rf-artist__hero"
      >
        <div className="rf-artist__hero-inner">
          <div className="rf-artist__hero-art">
            {heroUrl ? (
              <KenBurnsCover src={heroUrl} alt="" />
            ) : (
              <div className="rf-artist__hero-art-fallback">
                <Icon name="user" size={64} />
              </div>
            )}
          </div>
          <h1 className="rf-artist__name">
            {detail?.name ?? ' '}
          </h1>
          <div className="rf-artist__sub">
            {followerCount !== null && (
              <span className="rf-artist__sub-item">
                {t('redesign.artist.followers', {
                  count: fmtCount(followerCount),
                })}
              </span>
            )}
            {detail?.track_count != null && (
              <span className="rf-artist__sub-item">
                {t('redesign.artist.tracksCount', {
                  count: fmtCount(detail.track_count),
                })}
              </span>
            )}
            {sourceName && sourcePageUrl && (
              <MotionPress
                variant="ghost"
                haptic="light"
                onClick={handleOpenSource}
                className="rf-artist__source-btn"
              >
                <Icon name="link-external" size={12} />
                <span>{sourceName}</span>
              </MotionPress>
            )}
            {sourceName && !sourcePageUrl && (
              <span className="rf-artist__sub-item">
                {sourceName}
              </span>
            )}
          </div>
          <div className="rf-artist__actions">
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
            <MotionPress
              variant="ghost"
              haptic="selection"
              onClick={() => {
                void handleShuffle()
              }}
              disabled={!tracks || tracks.length === 0}
            >
              <Icon name="shuffle" size={16} />
              <span>{t('redesign.artist.shuffle')}</span>
            </MotionPress>
            <MotionPress
              variant={following ? 'primary' : 'ghost'}
              haptic="selection"
              onClick={() => {
                void handleFollow()
              }}
              disabled={followBusy}
              ariaLabel={
                following
                  ? t('redesign.artist.followingAria')
                  : t('redesign.artist.followAria')
              }
              className="rf-artist__follow-btn"
              data-active={following ? 'true' : 'false'}
            >
              <MorphIcon
                name="heart"
                size={16}
                filled={following}
              />
              <span>
                {following
                  ? t('redesign.artist.following')
                  : t('redesign.artist.follow')}
              </span>
            </MotionPress>
          </div>
        </div>
      </AmbientStage>

      <m.div
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
        className="rf-artist__sections"
      >
        <section className="rf-artist__section">
          <h2 className="rf-artist__section-title">
            {t('redesign.artist.topTracks')}
          </h2>
          <TrackList
            tracks={tracks}
            emptyMessage={t('redesign.artist.noTracks')}
          />
        </section>

        {detail?.bio && detail.bio.trim() && (
          <section className="rf-artist__section">
            <h2 className="rf-artist__section-title">
              {t('redesign.artist.about')}
            </h2>
            <p className="rf-artist__bio">{detail.bio}</p>
            {(detail.country || detail.birthplace) && (
              <p className="rf-artist__meta">
                {[detail.birthplace, detail.country]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            )}
          </section>
        )}

        {similar.length > 0 && (
          <section className="rf-artist__section">
            <h2 className="rf-artist__section-title">
              {t('redesign.artist.similar')}
            </h2>
            <HorizontalSnap
              items={similar}
              ariaLabel={t('redesign.artist.similar')}
              renderItem={(s) => (
                <button
                  type="button"
                  className="rf-artist__similar-card"
                  onClick={() => handleOpenSimilar(s.id)}
                >
                  <div className="rf-artist__similar-art">
                    {similarImageUrl(s) ? (
                      <img
                        src={similarImageUrl(s) || ''}
                        alt=""
                        loading="lazy"
                        decoding="async"
                      />
                    ) : (
                      <Icon name="user" size={32} />
                    )}
                  </div>
                  <span className="rf-artist__similar-name">
                    {s.name}
                  </span>
                </button>
              )}
            />
          </section>
        )}

        <section className="rf-artist__footer">
          {externalWebsiteUrl && (
            <MotionPress
              variant="ghost"
              haptic="light"
              onClick={handleOpenExternalSite}
              className="rf-artist__footer-btn"
            >
              <Icon name="link-external" size={14} />
              <span>{t('redesign.artist.openExternal')}</span>
            </MotionPress>
          )}
          <MotionPress
            variant="ghost"
            haptic="light"
            onClick={() => {
              toast.info(t('redesign.artist.reportSoon'))
            }}
            className="rf-artist__footer-btn"
          >
            <Icon name="flag" size={14} />
            <span>{t('redesign.artist.report')}</span>
          </MotionPress>
        </section>
      </m.div>
    </section>
  )
}
