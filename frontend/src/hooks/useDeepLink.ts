import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import { useOptionalPrefetch } from '@/store/PrefetchContext'

export function useTrackDeepLink() {
  const { trackId } = useParams<{ trackId: string }>()
  const { playTrack, openCard } = usePlayerActions()
  const prefetch = useOptionalPrefetch()
  const navigate = useNavigate()

  useEffect(() => {
    if (!trackId) return
    api.getTrack(Number(trackId))
      .then((track) => {
        try {
          void prefetch?.prefetch([track], {
            context: 'deep_link',
            replaceContext: true,
          })
        } catch {
          /* ignore */
        }
        playTrack(track)
        openCard()
        navigate('/', { replace: true })
      })
      .catch(() => {
        navigate('/', { replace: true })
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackId])
}
