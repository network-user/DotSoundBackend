import { useEffect, useState } from 'react'

const MEDIA = '(max-width: 720px)'

export function useIsNarrowLayout(): boolean {
  const [narrow, setNarrow] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.matchMedia(MEDIA).matches,
  )
  useEffect(() => {
    const mq = window.matchMedia(MEDIA)
    setNarrow(mq.matches)
    const on = () => setNarrow(mq.matches)
    mq.addEventListener('change', on)
    return () =>
      mq.removeEventListener('change', on)
  }, [])
  return narrow
}
