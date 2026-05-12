import { useCallback, useEffect, useState } from 'react'

interface NavItem {
  id: string
  label: string
}

interface Props {
  items: NavItem[]
  rootMargin?: string
  scrollRoot?: HTMLElement | null
}

export function AdminPageNav({
  items,
  rootMargin,
  scrollRoot,
}: Props) {
  const [active, setActive] = useState<string | null>(
    items[0]?.id ?? null,
  )

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return
    const targets = items
      .map(({ id }) => document.getElementById(id))
      .filter((el): el is HTMLElement => Boolean(el))
    if (targets.length === 0) return
    const seen = new Map<string, number>()
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          seen.set(e.target.id, e.intersectionRatio)
        }
        let bestId: string | null = null
        let bestRatio = 0
        seen.forEach((ratio, id) => {
          if (ratio > 0 && ratio > bestRatio) {
            bestId = id
            bestRatio = ratio
          }
        })
        if (bestId) setActive(bestId)
      },
      {
        root: scrollRoot ?? null,
        rootMargin: rootMargin ?? '-30% 0px -50% 0px',
        threshold: [0, 0.2, 0.6, 1],
      },
    )
    targets.forEach((t) => io.observe(t))
    return () => io.disconnect()
  }, [items, rootMargin, scrollRoot])

  const onClick = useCallback((id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setActive(id)
  }, [])

  if (items.length === 0) return null

  return (
    <nav className="admin-page-nav" aria-label="Page sections">
      <div className="admin-page-nav__scroll">
        {items.map((it) => (
          <button
            key={it.id}
            type="button"
            className={
              active === it.id
                ? 'admin-page-nav__pill is-active'
                : 'admin-page-nav__pill'
            }
            onClick={() => onClick(it.id)}
            aria-current={active === it.id ? 'true' : undefined}
          >
            {it.label}
          </button>
        ))}
      </div>
    </nav>
  )
}
