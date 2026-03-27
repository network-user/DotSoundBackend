import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'

interface LikesContextValue {
  isLiked: (trackId: number) => boolean
  toggleLike: (trackId: number) => Promise<void>
}

const LikesContext = createContext<LikesContextValue | null>(null)

export function LikesProvider({ children }: { children: ReactNode }) {
  const [likedIds, setLikedIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!userId) return
    api.getLikedTracks(userId).then((data) => {
      setLikedIds(new Set(data.items.map((t) => t.id)))
    }).catch(() => {})
  }, [])

  const isLiked = (trackId: number) => likedIds.has(trackId)

  const toggleLike = async (trackId: number) => {
    if (!userId) return
    const { liked } = await api.toggleLike(userId, trackId)
    setLikedIds((prev) => {
      const next = new Set(prev)
      if (liked) next.add(trackId)
      else next.delete(trackId)
      return next
    })
  }

  return (
    <LikesContext.Provider value={{ isLiked, toggleLike }}>
      {children}
    </LikesContext.Provider>
  )
}

export function useLikes() {
  const ctx = useContext(LikesContext)
  if (!ctx) throw new Error('useLikes must be used within LikesProvider')
  return ctx
}
