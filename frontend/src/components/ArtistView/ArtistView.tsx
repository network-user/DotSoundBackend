import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import type { ArtistDetail, Track } from '@/types/api'

interface Props {
  artistId: number
  onClose: () => void
}

function hasAnyInfo(artist: ArtistDetail): boolean {
  return Boolean(
    artist.bio ||
      artist.birth_date ||
      artist.birthplace ||
      artist.country ||
      artist.website_url,
  )
}

export function ArtistView({
  artistId,
  onClose,
}: Props) {
  const { t } = useTranslation()
  const [artist, setArtist] =
    useState<ArtistDetail | null>(null)
  const [tracks, setTracks] = useState<
    Track[] | null
  >(null)
  const [bioOpen, setBioOpen] = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [enrichError, setEnrichError] = useState<
    string | null
  >(null)
  const isAdmin = getIsAdmin()

  useEffect(() => {
    let cancelled = false
    setArtist(null)
    setTracks(null)
    setBioOpen(false)

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

    return () => {
      cancelled = true
    }
  }, [artistId])

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

  if (!artist) {
    return (
      <div className="author-view">
        <div className="author-view-header">
          <button
            className="author-back-btn icon-btn"
            onClick={onClose}
          >
            <Icon name="chevron" size={18} />
            {t('common.back', {
              defaultValue: 'Назад',
            })}
          </button>
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

  const metaParts: string[] = []
  if (artist.age !== null && artist.age !== undefined) {
    metaParts.push(t('artist.age', { count: artist.age }))
  }
  if (artist.birthplace) {
    metaParts.push(artist.birthplace)
  } else if (artist.country) {
    metaParts.push(artist.country)
  }
  if (metaParts.length === 0) {
    metaParts.push(t('artist.performer'))
  }
  const infoKnown = hasAnyInfo(artist)
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

  return (
    <div className="author-view">
      <div className="author-view-header">
        <button
          className="author-back-btn icon-btn"
          onClick={onClose}
        >
          <Icon name="chevron" size={18} />
          {t('common.back', {
            defaultValue: 'Назад',
          })}
        </button>
      </div>

      <div className="author-hero">
        <div className="profile-avatar">
          {artist.image_url ? (
            <img
              src={artist.image_url}
              alt={artist.name}
            />
          ) : (
            artist.name
              .charAt(0)
              .toUpperCase()
          )}
        </div>
        <div className="author-name">
          {artist.name}
        </div>
        <p
          className="author-username"
          style={{ marginTop: 8 }}
        >
          {metaParts.join(' • ')}
        </p>

        {isAdmin && (
          <div
            className="artist-admin-actions"
            style={{ marginTop: 12 }}
          >
            <button
              className="btn-primary artist-enrich-btn"
              onClick={handleEnrich}
              disabled={enriching}
            >
              {enriching
                ? t('artist.enrich_loading')
                : t('artist.enrich_button')}
            </button>
            {enrichError && (
              <div
                className="form-error"
                style={{ marginTop: 6 }}
              >
                {enrichError}
              </div>
            )}
          </div>
        )}
      </div>

      {artist.bio && (
        <div className="artist-bio-section">
          <button
            className="section-header artist-bio-toggle"
            onClick={() =>
              setBioOpen((v) => !v)
            }
          >
            <span className="section-title">
              {t('artist.bio_title')}
            </span>
            <span className="artist-bio-chevron">
              <Icon
                name="chevron"
                size={14}
              />
            </span>
          </button>
          <div
            className={
              bioOpen
                ? 'artist-bio-text'
                : 'artist-bio-text artist-bio-collapsed'
            }
          >
            {artist.bio}
          </div>
          {!bioOpen && (
            <button
              className="artist-bio-more"
              onClick={() => setBioOpen(true)}
            >
              {t('artist.bio_show_more')}
            </button>
          )}
          {bioOpen && (
            <button
              className="artist-bio-more"
              onClick={() => setBioOpen(false)}
            >
              {t('artist.bio_show_less')}
            </button>
          )}
        </div>
      )}

      {(artist.birth_date ||
        artist.birthplace ||
        artist.website_url) && (
        <div className="artist-meta-row">
          {artist.birth_date && (
            <span>
              {t('artist.born')}:{' '}
              {artist.birth_date}
            </span>
          )}
          {artist.birthplace && (
            <span>
              {t('artist.birthplace')}:{' '}
              {artist.birthplace}
            </span>
          )}
          {artist.website_url && (
            <a
              href={artist.website_url}
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

      <div className="section-header">
        <span className="section-title">
          {t('artist.tracks_title')}
        </span>
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage={t('artist.tracks_empty')}
      />
    </div>
  )
}
