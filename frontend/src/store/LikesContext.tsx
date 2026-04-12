import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
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

  const reloadLikes = () => setAuthTick((n) => n + 1)

  useEffect(() => {
    const uid = getUserId()
    if (!uid) return
    api.getLikedTracks(uid).then((data) => {
      setLikedIds(new Set(data.items.map((t) => t.id)))
    }).catch(() => {})
  }, [authTick])

  const isLiked = (trackId: number) => likedIds.has(trackId)
  const isDisliked = (trackId: number) => dislikedIds.has(trackId)

  const toggleLike = async (trackId: number) => {
    const uid = getUserId()
    if (!uid) return
    try {
      const { liked } = await api.toggleLike(uid, trackId)
      setLikedIds((prev) => {
        const next = new Set(prev)
        if (liked) next.add(trackId)
        else next.delete(trackId)
        return next
      })
      if (liked) {
        setDislikedIds((prev) => {
          const next = new Set(prev)
          next.delete(trackId)
          return next
        })
      }
    } catch (e) {
      console.error('toggleLike failed', e)
    }
  }

  const toggleDislike = async (trackId: number) => {
    const uid = getUserId()
    if (!uid) return
    try {
      const { disliked } = await api.toggleDislike(uid, trackId)
      setDislikedIds((prev) => {
        const next = new Set(prev)
        if (disliked) next.add(trackId)
        else next.delete(trackId)
        return next
      })
      if (disliked) {
        setLikedIds((prev) => {
          const next = new Set(prev)
          next.delete(trackId)
          return next
        })
      }
    } catch (e) {
      console.error('toggleDislike failed', e)
    }
  }

  return (
    <LikesContext.Provider value={{ isLiked, isDisliked, toggleLike, toggleDislike, reloadLikes }}>
      {children}
    </LikesContext.Provider>
  )
}

export function useLikes() {
  const ctx = useContext(LikesContext)
  if (!ctx) throw new Error('useLikes must be used within LikesProvider')
  return ctx
}
