import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'

export function useTrackDeepLink() {
  const { trackId } = useParams<{ trackId: string }>()
  const { playTrack } = usePlayerActions()
  const navigate = useNavigate()

  useEffect(() => {
    if (!trackId) return
    api.getTrack(Number(trackId))
      .then((track) => {
        playTrack(track)
        navigate('/', { replace: true })
      })
      .catch(() => {
        navigate('/', { replace: true })
      })
  }, [trackId])
}
