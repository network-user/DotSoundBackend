import {
  type ReactNode,
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
  const [activeIndex, setActiveIndex] = useState(0)
  const [canArrow, setCanArrow] = useState({
    left: false,
    right: false,
  })

  useEffect(() => {
    const el = trackRef.current
    if (!el) return
    const items = Array.from(
      el.querySelectorAll<HTMLElement>('[data-snap-item]'),
    )
    if (items.length === 0) return

    const io = new IntersectionObserver(
      (entries) => {
        let bestIdx = activeIndex
        let bestRatio = 0
        for (const entry of entries) {
          const idx = Number(
            (entry.target as HTMLElement).dataset.snapIndex ?? '0',
          )
          if (entry.intersectionRatio > bestRatio) {
            bestRatio = entry.intersectionRatio
            bestIdx = idx
          }
        }
        if (bestRatio > 0) setActiveIndex(bestIdx)
      },
      {
        root: el,
        threshold: [0.4, 0.6, 0.8],
      },
    )
    items.forEach((it) => io.observe(it))
    return () => io.disconnect()
  }, [items.length, activeIndex])

  useEffect(() => {
    const el = trackRef.current
    if (!el) return
    const update = () => {
      setCanArrow({
        left: el.scrollLeft > 4,
        right:
          el.scrollLeft + el.clientWidth <
          el.scrollWidth - 4,
      })
      if (parallax) {
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
      }
    }
    update()
    el.addEventListener('scroll', update, {
      passive: true,
    })
    window.addEventListener('resize', update)
    return () => {
      el.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [parallax])

  const scrollByPage = (dir: 1 | -1) => {
    const el = trackRef.current
    if (!el) return
    el.scrollBy({
      left: dir * el.clientWidth * 0.85,
      behavior: reduce ? 'auto' : 'smooth',
    })
  }

  return (
    <div
      className={[
        'h-snap',
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
      {pageDots && items.length > 1 && (
        <div
          className="h-snap__dots"
          aria-hidden="true"
        >
          {items.map((_, idx) => (
            <span
              key={idx}
              className={[
                'h-snap__dot',
                idx === activeIndex
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
