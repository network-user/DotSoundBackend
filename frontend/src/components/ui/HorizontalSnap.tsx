import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { Icon } from '@/components/Icon/Icon'
import { useReducedMotion } from '@/lib/motion'

export interface HorizontalSnapProps<T> {
  items: T[]
  renderItem: (item: T, index: number) => ReactNode
  pageDots?: boolean
  showArrows?: 'never' | 'md+'
  parallax?: boolean
  className?: string
  ariaLabel?: string
}

export function HorizontalSnap<T>({
  items,
  renderItem,
  pageDots = false,
  showArrows = 'md+',
  parallax = false,
  className,
  ariaLabel,
}: HorizontalSnapProps<T>) {
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

  const updateTrackMeta = useCallback(() => {
    const el = trackRef.current
    if (!el) return
    const maxScrollLeft = Math.max(
      0,
      el.scrollWidth - el.clientWidth,
    )
    const hasOverflow = maxScrollLeft > 4
    const totalPages = Math.max(
      1,
      Math.ceil(el.scrollWidth / Math.max(1, el.clientWidth)),
    )
    const activePage =
      totalPages <= 1 || maxScrollLeft <= 0
        ? 0
        : Math.round(
            (el.scrollLeft / maxScrollLeft) * (totalPages - 1),
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

    if (!parallax) return
    const items = el.querySelectorAll<HTMLElement>(
      '[data-snap-item]',
    )
    items.forEach((it) => {
      const r = it.getBoundingClientRect()
      const er = el.getBoundingClientRect()
      const center =
        r.left + r.width / 2 -
        (er.left + er.width / 2)
      const norm = Math.max(
        -1,
        Math.min(1, center / er.width),
      )
      it.style.setProperty(
        '--snap-parallax',
        norm.toFixed(3),
      )
    })
  }, [parallax])

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
  }, [items.length, updateTrackMeta])

  const scrollByPage = (dir: 1 | -1) => {
    const el = trackRef.current
    if (!el) return
    el.scrollBy({
      left: dir * el.clientWidth * 0.85,
      behavior: reduce ? 'auto' : 'smooth',
    })
  }

  const visibleDots = Math.min(4, pageMeta.totalPages)
  const activeDot =
    visibleDots <= 1 || pageMeta.totalPages <= 1
      ? 0
      : Math.round(
          (pageMeta.activePage / (pageMeta.totalPages - 1)) *
            (visibleDots - 1),
        )

  return (
    <div
      className={[
        'h-snap',
        isCompact ? 'h-snap--compact' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      aria-label={ariaLabel}
    >
      <div
        className="h-snap__track"
        ref={trackRef}
        role="list"
      >
        {items.map((it, idx) => (
          <div
            key={idx}
            className="h-snap__item"
            role="listitem"
            data-snap-item=""
            data-snap-index={idx}
          >
            {renderItem(it, idx)}
          </div>
        ))}
      </div>
      {showArrows === 'md+' && (
        <>
          <button
            type="button"
            className="h-snap__arrow h-snap__arrow--left"
            aria-label="Назад"
            disabled={!canArrow.left}
            onClick={() => scrollByPage(-1)}
          >
            <Icon name="arrow-left" size={16} />
          </button>
          <button
            type="button"
            className="h-snap__arrow h-snap__arrow--right"
            aria-label="Вперёд"
            disabled={!canArrow.right}
            onClick={() => scrollByPage(1)}
          >
            <Icon name="arrow-right" size={16} />
          </button>
        </>
      )}
      {pageDots && visibleDots > 1 && (
        <div
          className="h-snap__dots"
          aria-hidden="true"
        >
          {Array.from({ length: visibleDots }).map((_, idx) => (
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
          ))}
        </div>
      )}
    </div>
  )
}
