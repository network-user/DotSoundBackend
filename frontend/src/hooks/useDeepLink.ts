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
  }, [])
}
