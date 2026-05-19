import { useEffect, useRef } from 'react'

type UseAutoLoadMoreArgs = {
  enabled: boolean
  loading: boolean
  onLoadMore: () => void
  rootMargin?: string
}

export function useAutoLoadMore({
  enabled,
  loading,
  onLoadMore,
  rootMargin = '240px',
}: UseAutoLoadMoreArgs) {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || !enabled || loading) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          onLoadMore()
        }
      },
      { rootMargin },
    )
    observer.observe(el)
    return () => {
      observer.disconnect()
    }
  }, [enabled, loading, onLoadMore, rootMargin])

  return ref
}
