import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'

interface LikesContextValue {
  isLiked: (trackId: number) => boolean
  isDisliked: (trackId: number) => boolean
  toggleLike: (trackId: number) => Promise<void>
  toggleDislike: (trackId: number) => Promise<void>
  reloadLikes: () => void
}

const LikesContext = createContext<LikesContextValue | null>(null)

export function LikesProvider({ children }: { children: ReactNode }) {
  const [likedIds, setLikedIds] = useState<Set<number>>(new Set())
  const [dislikedIds, setDislikedIds] = useState<Set<number>>(new Set())
  const [authTick, setAuthTick] = useState(0)

  const reloadLikes = useCallback(
    () => setAuthTick((n) => n + 1),
    [],
  )

  useEffect(() => {
    const uid = getUserId()
    if (!uid) return
    api.getLikedTracks(uid, 1, 200).then((data) => {
      setLikedIds(new Set(data.items.map((t) => t.id)))
    }).catch(() => {})
  }, [authTick])

  const isLiked = useCallback(
    (trackId: number) => likedIds.has(trackId),
    [likedIds],
  )

  const isDisliked = useCallback(
    (trackId: number) => dislikedIds.has(trackId),
    [dislikedIds],
  )

  const toggleLike = useCallback(async (trackId: number) => {
    const uid = getUserId()
    if (!uid) return
    try {
      const { liked, playback_variant_track_ids } =
        await api.toggleLike(uid, trackId)
      const ids =
        playback_variant_track_ids.length > 0
          ? playback_variant_track_ids
          : [trackId]
      setLikedIds((prev) => {
        const next = new Set(prev)
        if (liked) {
          for (const id of ids) next.add(id)
        } else {
          for (const id of ids) next.delete(id)
        }
        return next
      })
      if (liked) {
        setDislikedIds((prev) => {
          const next = new Set(prev)
          for (const id of ids) next.delete(id)
          return next
        })
      }
    } catch (e) {
      console.error('toggleLike failed', e)
    }
  }, [])

  const toggleDislike = useCallback(async (trackId: number) => {
    const uid = getUserId()
    if (!uid) return
    try {
      const { disliked, playback_variant_track_ids } =
        await api.toggleDislike(uid, trackId)
      const ids =
        playback_variant_track_ids.length > 0
          ? playback_variant_track_ids
          : [trackId]
      setDislikedIds((prev) => {
        const next = new Set(prev)
        if (disliked) {
          for (const id of ids) next.add(id)
        } else {
          for (const id of ids) next.delete(id)
        }
        return next
      })
      if (disliked) {
        setLikedIds((prev) => {
          const next = new Set(prev)
          for (const id of ids) next.delete(id)
          return next
        })
      }
    } catch (e) {
      console.error('toggleDislike failed', e)
    }
  }, [])

  const value = useMemo(
    () => ({ isLiked, isDisliked, toggleLike, toggleDislike, reloadLikes }),
    [isLiked, isDisliked, toggleLike, toggleDislike, reloadLikes],
  )

  return (
    <LikesContext.Provider value={value}>
      {children}
    </LikesContext.Provider>
  )
}

export function useLikes() {
  const ctx = useContext(LikesContext)
  if (!ctx) throw new Error('useLikes must be used within LikesProvider')
  return ctx
}
