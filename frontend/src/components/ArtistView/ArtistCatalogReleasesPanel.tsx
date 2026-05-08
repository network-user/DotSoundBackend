import {
  type MouseEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'

import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useExitTransition } from '@/hooks/useExitTransition'
import { useHorizontalPointerDragScroll } from '@/hooks/useHorizontalPointerDragScroll'
import {
  HORIZONTAL_PAGE_SCROLL_MS,
  scrollHorizontalByOnePage,
} from '@/lib/horizontalScrollAnimate'
import { useReducedMotion } from '@/lib/motion'
import type { ArtistCatalogReleaseSummary } from '@/types/api'

const RELEASES_PER_SLIDE = 3

const STATION_RELEASE_KIND = 'dotsound_sc_artist_station'

interface Props {
  artistDisplayName: string
  items: ArtistCatalogReleaseSummary[]
  loadError: boolean
  isAdmin: boolean
  onSelectRelease: (releaseId: number) => void
}

export function ArtistCatalogReleasesPanel({
  artistDisplayName,
  items,
  loadError,
  isAdmin,
  onSelectRelease,
}: Props) {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const trackRef = useRef<HTMLDivElement | null>(null)
  const [canArrow, setCanArrow] = useState({
    left: false,
    right: false,
  })
  const [pageMeta, setPageMeta] = useState({
    totalPages: 1,
    activePage: 0,
  })
  const [isCompact, setIsCompact] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const modalExit = useExitTransition(modalOpen, 220)

  const orderedItems = useMemo(() => {
    if (!items.length) {
      return items
    }
    const stations = items.filter(
      (i) => i.release_kind === STATION_RELEASE_KIND,
    )
    const rest = items.filter(
      (i) => i.release_kind !== STATION_RELEASE_KIND,
    )
    return [...stations, ...rest]
  }, [items])

  const slides = useMemo(() => {
    if (!orderedItems.length) {
      return [] as ArtistCatalogReleaseSummary[][]
    }
    const chunks: ArtistCatalogReleaseSummary[][] = []
    for (
      let i = 0;
      i < orderedItems.length;
      i += RELEASES_PER_SLIDE
    ) {
      chunks.push(
        orderedItems.slice(i, i + RELEASES_PER_SLIDE),
      )
    }
    return chunks
  }, [orderedItems])

  const updateTrackMeta = useCallback(() => {
    const el = trackRef.current
    if (!el) return
    const maxScrollLeft = Math.max(
      0,
      el.scrollWidth - el.clientWidth,
    )
    const hasOverflow = maxScrollLeft > 4
    const pageW = Math.max(1, el.clientWidth)
    const totalPages = Math.max(
      1,
      Math.ceil(el.scrollWidth / pageW),
    )
    const activePage =
      totalPages <= 1 || maxScrollLeft <= 0
        ? 0
        : Math.round(
            (el.scrollLeft / maxScrollLeft) *
              (totalPages - 1),
          )

    setCanArrow({
      left: el.scrollLeft > 4,
      right:
        el.scrollLeft + el.clientWidth <
        el.scrollWidth - 4,
    })
    setIsCompact(!hasOverflow)
    setPageMeta({
      totalPages,
      activePage: Math.max(
        0,
        Math.min(activePage, totalPages - 1),
      ),
    })
  }, [])

  useEffect(() => {
    const el = trackRef.current
    if (!el) return
    updateTrackMeta()
    el.addEventListener('scroll', updateTrackMeta, {
      passive: true,
    })
    window.addEventListener('resize', updateTrackMeta)
    return () => {
      el.removeEventListener('scroll', updateTrackMeta)
      window.removeEventListener('resize', updateTrackMeta)
    }
  }, [slides.length, updateTrackMeta])

  useHorizontalPointerDragScroll(
    trackRef,
    slides.length > 1,
    slides.length,
  )

  const scrollBySlide = (dir: 1 | -1) => {
    const el = trackRef.current
    if (!el) return
    scrollHorizontalByOnePage(el, dir, {
      durationMs: HORIZONTAL_PAGE_SCROLL_MS,
      instant: Boolean(reduce),
    })
  }

  const showSeeAll =
    orderedItems.length > RELEASES_PER_SLIDE

  const sectionTitle = t('artist.catalog_releases_title')
  const similarStationTitle = t(
    'redesign.artist.catalogReleasesSimilar',
    { name: artistDisplayName || '—' },
  )
  const titleCount =
    orderedItems.length > 0
      ? ` (${orderedItems.length})`
      : ''

  useEffect(() => {
    if (!modalOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setModalOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [modalOpen])

  const closeModal = () => setModalOpen(false)

  const handleBackdrop = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      closeModal()
    }
  }

  const visibleDots = Math.min(6, pageMeta.totalPages)
  const activeDot =
    visibleDots <= 1 || pageMeta.totalPages <= 1
      ? 0
      : Math.round(
          (pageMeta.activePage /
            (pageMeta.totalPages - 1)) *
            (visibleDots - 1),
        )

  const renderReleaseCard = (
    r: ArtistCatalogReleaseSummary,
  ) => {
    const y = r.released_at?.match(/^(\d{4})/)?.[1]
    const metaBits: string[] = []
    if (y) metaBits.push(y)
    metaBits.push(
      t('artist.catalog_release_card_tracks', {
        count: r.track_count,
      }),
    )
    const isScStation =
      r.release_kind === STATION_RELEASE_KIND
    const cardTitle = isScStation
      ? similarStationTitle
      : r.title
    return (
      <MotionPress
        type="button"
        variant="subtle"
        haptic="light"
        className={
          isScStation
            ? 'artist-catalog-release-card artist-catalog-release-card-station'
            : 'artist-catalog-release-card'
        }
        onClick={() => onSelectRelease(r.id)}
      >
        <CoverImage coverKey={r.cover_key} size={56} />
        <div className="artist-catalog-release-card-text">
          <div className="artist-catalog-release-card-title">
            {cardTitle}
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
  }

  if (loadError) {
    return (
      <div className="artist-catalog-releases">
        <h2 className="rf-artist__section-title">
          {sectionTitle}
        </h2>
        <div className="artist-empty-info">
          {t('artist.catalog_releases_load_error')}
        </div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="artist-catalog-releases">
        <h2 className="rf-artist__section-title">
          {sectionTitle}
        </h2>
        <div className="artist-empty-info">
          {isAdmin
            ? t('artist.catalog_releases_empty_admin')
            : t('artist.catalog_releases_empty')}
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="rf-artist-releases__head">
        <h2 className="rf-artist__section-title rf-artist-releases__title">
          {sectionTitle}
          {titleCount}
        </h2>
        {showSeeAll && (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="rf-artist-releases__see-all"
            onClick={() => setModalOpen(true)}
          >
            <span>{t('redesign.artist.topTracksSeeAll')}</span>
            <Icon name="chevron-right" size={14} />
          </MotionPress>
        )}
      </div>

      <div
        className={[
          'rf-artist-releases',
          isCompact ? 'rf-artist-releases--compact' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <div
          className="rf-artist-releases__viewport"
          ref={trackRef}
          role="list"
        >
          {slides.map((chunk, si) => (
            <div
              key={`rel-slide-${si}`}
              className="rf-artist-releases__slide"
              role="listitem"
            >
              {chunk.map((r) => (
                <div
                  key={r.id}
                  className="rf-artist-releases__row"
                >
                  {renderReleaseCard(r)}
                </div>
              ))}
            </div>
          ))}
        </div>
        <button
          type="button"
          className="h-snap__arrow h-snap__arrow--left"
          aria-label={t('redesign.artist.topTracksPrev')}
          disabled={!canArrow.left}
          onClick={() => scrollBySlide(-1)}
        >
          <Icon name="arrow-left" size={16} />
        </button>
        <button
          type="button"
          className="h-snap__arrow h-snap__arrow--right"
          aria-label={t('redesign.artist.topTracksNext')}
          disabled={!canArrow.right}
          onClick={() => scrollBySlide(1)}
        >
          <Icon name="arrow-right" size={16} />
        </button>
      </div>

      {visibleDots > 1 && (
        <div
          className="h-snap__dots rf-artist-releases__dots"
          aria-hidden="true"
        >
          {Array.from({ length: visibleDots }).map(
            (_, idx) => (
              <span
                key={idx}
                className={[
                  'h-snap__dot',
                  idx === activeDot
                    ? 'h-snap__dot--active'
                    : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              />
            ),
          )}
        </div>
      )}

      {modalExit.mounted && (
        <div
          className={`modal${modalExit.cls}`}
          onClick={handleBackdrop}
          role="presentation"
        >
          <div
            className="modal-content rf-artist-releases-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rf-artist-releases-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header rf-artist-releases-modal__header">
              <h3 id="rf-artist-releases-modal-title">
                {sectionTitle}
                {titleCount}
              </h3>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t(
                  'redesign.artist.catalogReleasesModalCloseAria',
                )}
                onClick={closeModal}
              >
                <Icon name="x" size={18} />
              </MotionPress>
            </div>
            <div className="rf-artist-releases-modal__body">
              <div className="artist-catalog-releases-modal-grid">
                {orderedItems.map((r) => (
                  <div key={r.id}>
                    {renderReleaseCard(r)}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
