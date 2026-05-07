import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import type {
  ArtistCatalogReleaseDetail,
  Track,
} from '@/types/api'

interface Props {
  artistId: number
  releaseId: number
  artistName: string
  onBack: () => void
}

function formatReleaseDate(iso: string | null): string | null {
  if (!iso) return null
  const m = iso.match(/^(\d{4})/)
  return m ? m[1] : iso
}

export function ArtistCatalogReleasePanel({
  artistId,
  releaseId,
  artistName,
  onBack,
}: Props) {
  const { t } = useTranslation()
  const [detail, setDetail] =
    useState<ArtistCatalogReleaseDetail | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setDetail(null)
    setFailed(false)
    api
      .getArtistCatalogRelease(artistId, releaseId)
      .then((d) => {
        if (!cancelled) setDetail(d)
      })
      .catch(() => {
        if (!cancelled) {
          setDetail(null)
          setFailed(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [artistId, releaseId])

  const orderedTracks = useMemo<Track[] | null>(() => {
    if (!detail) return null
    return detail.tracks.map((row) => row.track)
  }, [detail])

  const yearLabel = detail
    ? formatReleaseDate(detail.released_at)
    : null
  const metaParts: string[] = [artistName]
  if (yearLabel) metaParts.push(yearLabel)
  if (detail?.release_kind) {
    metaParts.push(detail.release_kind)
  }

  return (
    <div className="author-view artist-catalog-release-view">
      <div className="author-view-header">
        <MotionPress
          type="button"
          variant="ghost"
          haptic="light"
          className="author-back-btn icon-btn"
          onClick={onBack}
        >
          <Icon name="chevron" size={18} />
          {t('artist.catalog_release_back', {
            defaultValue: 'Back to artist',
          })}
        </MotionPress>
      </div>

      {failed && (
        <div className="artist-catalog-release-error">
          <p>{t('artist.catalog_release_load_error')}</p>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="btn-secondary"
            onClick={onBack}
          >
            {t('common.back', { defaultValue: 'Back' })}
          </MotionPress>
        </div>
      )}

      {!failed && detail && (
        <>
          <div className="artist-catalog-release-hero">
            <div className="artist-catalog-release-cover-wrap">
              <CoverImage coverKey={detail.cover_key} size={120} />
            </div>
            <h1 className="artist-catalog-release-title">
              {detail.title}
            </h1>
            <p className="artist-catalog-release-meta">
              {metaParts.join(' · ')}
            </p>
          </div>
          <div className="section-header">
            <span className="section-title">
              {t('artist.catalog_release_tracks')}
              {orderedTracks && orderedTracks.length > 0
                ? ` (${orderedTracks.length})`
                : ''}
            </span>
          </div>
          <TrackList
            tracks={orderedTracks}
            emptyMessage={t('artist.tracks_empty')}
          />
        </>
      )}

      {!failed && !detail && (
        <div className="artist-catalog-release-hero">
          <div className="profile-avatar skeleton" />
          <div
            className="skeleton"
            style={{
              width: '70%',
              maxWidth: 240,
              height: 22,
              borderRadius: 6,
              marginTop: 16,
            }}
          />
        </div>
      )}
    </div>
  )
}
