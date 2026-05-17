import {
  type MouseEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'

import { TrackCard } from '@/components/TrackCard/TrackCard'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useExitTransition } from '@/hooks/useExitTransition'
import { useHorizontalPointerDragScroll } from '@/hooks/useHorizontalPointerDragScroll'
import { api, getApiErrorMessage } from '@/lib/api'
import {
  HORIZONTAL_PAGE_SCROLL_MS,
  scrollHorizontalByOnePage,
} from '@/lib/horizontalScrollAnimate'
import { useReducedMotion } from '@/lib/motion'
import { showIsland } from '@/lib/island'
import type { Track } from '@/types/api'

const TRACKS_PER_SLIDE = 3

interface Props {
  artistId: number
  previewTracks: Track[] | null
  total: number | null
}

export function ArtistTopTracksPanel({
  artistId,
  previewTracks,
  total,
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
  const [modalTracks, setModalTracks] = useState<
    Track[] | null
  >(null)
  const [modalLoading, setModalLoading] = useState(false)

  const modalExit = useExitTransition(modalOpen, 220)

  const slides = useMemo(() => {
    if (!previewTracks?.length) {
      return [] as Track[][]
    }
    const chunks: Track[][] = []
    for (
      let i = 0;
      i < previewTracks.length;
      i += TRACKS_PER_SLIDE
    ) {
      chunks.push(
        previewTracks.slice(i, i + TRACKS_PER_SLIDE),
      )
    }
    return chunks
  }, [previewTracks])

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
    total !== null &&
    previewTracks !== null &&
    total > 0 &&
    (total > previewTracks.length || total > TRACKS_PER_SLIDE)

  const titleCount =
    total !== null && total > 0 ? ` (${total})` : ''

  useEffect(() => {
    if (!modalOpen) return
    let cancelled = false
    setModalTracks(null)
    setModalLoading(true)
    void (async () => {
      try {
        const items = await api.getAllArtistTracks(artistId)
        if (!cancelled) {
          setModalTracks(items)
        }
      } catch (e) {
        if (!cancelled) {
          showIsland({
            kind: 'error',
            title: getApiErrorMessage(
              e,
              t('redesign.artist.topTracksLoadError'),
            ),
            durationMs: 4000,
          })
          setModalTracks([])
        }
      } finally {
        if (!cancelled) {
          setModalLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [modalOpen, artistId, t])

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

  if (previewTracks === null) {
    return (
      <>
        <h2 className="rf-artist__section-title">
          {t('redesign.artist.topTracks')}
        </h2>
        <div className="track-list re-tl-root">
          <div className="loader" />
        </div>
      </>
    )
  }

  if (previewTracks.length === 0) {
    return (
      <>
        <h2 className="rf-artist__section-title">
          {t('redesign.artist.topTracks')}
        </h2>
        <TrackList
          tracks={previewTracks}
          emptyMessage={t('redesign.artist.noTracks')}
        />
      </>
    )
  }

  return (
    <>
      <div className="rf-artist-top-tracks__head">
        <h2 className="rf-artist__section-title rf-artist-top-tracks__title">
          {t('redesign.artist.topTracks')}
          {titleCount}
        </h2>
        {showSeeAll && (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="rf-artist-top-tracks__see-all"
            onClick={() => setModalOpen(true)}
          >
            <span>{t('redesign.artist.topTracksSeeAll')}</span>
            <Icon name="chevron-right" size={14} />
          </MotionPress>
        )}
      </div>

      <div
        className={[
          'rf-artist-top-tracks',
          isCompact ? 'rf-artist-top-tracks--compact' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <div
          className="rf-artist-top-tracks__viewport"
          ref={trackRef}
          role="list"
        >
          {slides.map((chunk, si) => (
            <div
              key={`slide-${si}`}
              className="rf-artist-top-tracks__slide"
              role="listitem"
            >
              {chunk.map((tr) => (
                <div
                  key={tr.id}
                  className="rf-artist-top-tracks__row"
                >
                  <TrackCard
                    track={tr}
                    contextTracks={previewTracks}
                  />
                </div>
              ))}
            </div>
          ))}
        </div>
        <button
          type="button"
          className="h-snap__arrow h-snap__arrow--left rf-artist-top-tracks__arrow"
          aria-label={t('redesign.artist.topTracksPrev')}
          disabled={!canArrow.left}
          onClick={() => scrollBySlide(-1)}
        >
          <Icon name="arrow-left" size={16} />
        </button>
        <button
          type="button"
          className="h-snap__arrow h-snap__arrow--right rf-artist-top-tracks__arrow"
          aria-label={t('redesign.artist.topTracksNext')}
          disabled={!canArrow.right}
          onClick={() => scrollBySlide(1)}
        >
          <Icon name="arrow-right" size={16} />
        </button>
      </div>

      {visibleDots > 1 && (
        <div
          className="h-snap__dots rf-artist-top-tracks__dots"
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
            className="modal-content rf-artist-tracks-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rf-artist-tracks-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header rf-artist-tracks-modal__header">
              <h3 id="rf-artist-tracks-modal-title">
                {t('redesign.artist.topTracks')}
                {total !== null && total > 0
                  ? ` (${total})`
                  : ''}
              </h3>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t(
                  'redesign.artist.topTracksModalCloseAria',
                )}
                onClick={closeModal}
              >
                <Icon name="x" size={18} />
              </MotionPress>
            </div>
            {modalLoading && (
              <div className="rf-artist-tracks-modal__loading">
                <div className="loader" />
              </div>
            )}
            {!modalLoading && (
              <div className="rf-artist-tracks-modal__body">
                <TrackList
                  tracks={modalTracks}
                  emptyMessage={t(
                    'redesign.artist.noTracks',
                  )}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
