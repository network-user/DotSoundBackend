import { useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import { useOptionalPrefetch } from '@/store/PrefetchContext'

export function useTrackDeepLink() {
  const { trackId } = useParams<{ trackId: string }>()
  const { playTrack, openCard } = usePlayerActions()
  const prefetch = useOptionalPrefetch()
  const navigate = useNavigate()
  const handledTrackIdRef = useRef<string | null>(null)
  const latestRef = useRef({
    navigate,
    openCard,
    playTrack,
    prefetch,
  })

  useEffect(() => {
    latestRef.current = {
      navigate,
      openCard,
      playTrack,
      prefetch,
    }
  }, [navigate, openCard, playTrack, prefetch])

  useEffect(() => {
    if (!trackId) return
    if (handledTrackIdRef.current === trackId) return

    const id = Number(trackId)
    if (!Number.isInteger(id) || id <= 0) {
      latestRef.current.navigate('/', { replace: true })
      return
    }

    handledTrackIdRef.current = trackId
    let cancelled = false

    api.getTrack(id)
      .then((track) => {
        if (cancelled) return
        const latest = latestRef.current
        try {
          void latest.prefetch?.prefetch([track], {
            context: 'deep_link',
            replaceContext: true,
          })
        } catch {
          /* ignore */
        }
        void latest.playTrack(track)
        latest.openCard()
        latest.navigate('/', { replace: true })
      })
      .catch(() => {
        if (cancelled) return
        latestRef.current.navigate('/', { replace: true })
      })

    return () => {
      cancelled = true
    }
  }, [trackId])
}
