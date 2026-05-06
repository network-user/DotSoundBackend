import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api, getApiErrorMessage } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import { useToast } from '@/components/ui/Toast'
import { queueMutation } from '@/lib/pendingEvents'

function _isNetworkError(e: unknown): boolean {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return true
  }
  return (
    e instanceof TypeError &&
    typeof e.message === 'string' &&
    /fetch|network/i.test(e.message)
  )
}

interface LikesContextValue {
  isLiked: (trackId: number) => boolean
  isDisliked: (trackId: number) => boolean
  toggleLike: (trackId: number) => Promise<void>
  toggleDislike: (trackId: number) => Promise<void>
  reloadLikes: () => void
}

const LikesContext = createContext<LikesContextValue | null>(null)

function _withIds(
  base: Set<number>,
  ids: number[],
  add: boolean,
): Set<number> {
  const next = new Set(base)
  if (add) {
    for (const id of ids) next.add(id)
  } else {
    for (const id of ids) next.delete(id)
  }
  return next
}

export function LikesProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const toast = useToast()
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

    const prevLiked = likedIds
    const prevDisliked = dislikedIds
    const willLike = !prevLiked.has(trackId)

    setLikedIds((prev) => _withIds(prev, [trackId], willLike))
    if (willLike) {
      setDislikedIds((prev) => _withIds(prev, [trackId], false))
    }

    try {
      const { liked, playback_variant_track_ids } =
        await api.toggleLike(uid, trackId)
      const ids =
        playback_variant_track_ids.length > 0
          ? playback_variant_track_ids
          : [trackId]
      setLikedIds((prev) => _withIds(prev, ids, liked))
      if (liked) {
        setDislikedIds((prev) => _withIds(prev, ids, false))
      }
    } catch (e) {
      if (_isNetworkError(e)) {
        await queueMutation(
          'POST',
          `/api/v1/likes/${uid}/${trackId}`,
        )
        return
      }
      setLikedIds(prevLiked)
      setDislikedIds(prevDisliked)
      const msg = getApiErrorMessage(
        e,
        t('likes.like_failed', 'Не удалось обновить лайк'),
      )
      toast.error(msg)
    }
  }, [likedIds, dislikedIds, t, toast])

  const toggleDislike = useCallback(async (trackId: number) => {
    const uid = getUserId()
    if (!uid) return

    const prevLiked = likedIds
    const prevDisliked = dislikedIds
    const willDislike = !prevDisliked.has(trackId)

    setDislikedIds((prev) => _withIds(prev, [trackId], willDislike))
    if (willDislike) {
      setLikedIds((prev) => _withIds(prev, [trackId], false))
    }

    try {
      const { disliked, playback_variant_track_ids } =
        await api.toggleDislike(uid, trackId)
      const ids =
        playback_variant_track_ids.length > 0
          ? playback_variant_track_ids
          : [trackId]
      setDislikedIds((prev) => _withIds(prev, ids, disliked))
      if (disliked) {
        setLikedIds((prev) => _withIds(prev, ids, false))
      }
    } catch (e) {
      if (_isNetworkError(e)) {
        await queueMutation(
          'POST',
          `/api/v1/dislikes/${uid}/${trackId}`,
        )
        return
      }
      setLikedIds(prevLiked)
      setDislikedIds(prevDisliked)
      const msg = getApiErrorMessage(
        e,
        t('likes.dislike_failed', 'Не удалось обновить дизлайк'),
      )
      toast.error(msg)
    }
  }, [likedIds, dislikedIds, t, toast])

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
