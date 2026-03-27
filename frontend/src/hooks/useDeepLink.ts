import { useEffect } from 'react'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'

export function useDeepLink() {
  const { playTrack } = usePlayer()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const trackId = params.get('track_id')
    if (!trackId) return
    api.getTrack(Number(trackId))
      .then((track) => playTrack(track))
      .catch(() => {})
  // playTrack is stable (defined in context), runs once on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
