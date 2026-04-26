import { useCallback, useState } from 'react'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

export function usePreviewQueue() {
  const [items, setItems] = useState<Track[]>([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (genre: string) => {
    setLoading(true)
    try {
      const r = await api.fetchGenrePreviewQueue(genre, 10)
      setItems(r.items)
      return r.items
    } catch {
      setItems([])
      return []
    } finally {
      setLoading(false)
    }
  }, [])

  const getSegmentPath = (trackId: number) =>
    api.trackPreviewSegmentPath(trackId)

  return { items, loading, load, getSegmentPath }
}
