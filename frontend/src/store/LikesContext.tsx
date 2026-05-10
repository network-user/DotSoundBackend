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
import { showIsland } from '@/lib/island'
import { queueMutation } from '@/lib/pendingEvents'
import {
  cancelAutoCache,
  ensureCachedIdsLoaded,
  getAutoCacheEnabled,
  getAutoCacheOnboardingShown,
  isOfflineCacheSupported,
  markAutoCacheOnboardingShown,
  queueAutoCache,
  removeTrack as removeOfflineTrack,
  setAutoCacheEnabled,
} from '@/lib/offlineCache'
import type { Track } from '@/types/api'

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
  toggleLike: (
    trackId: number,
    trackHint?: Track,
  ) => Promise<void>
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

  useEffect(() => {
    if (!isOfflineCacheSupported()) return
    void ensureCachedIdsLoaded()
  }, [])

  const offlineToastShownRef =
    useState<{ shown: boolean }>(() => ({
      shown: getAutoCacheOnboardingShown(),
    }))[0]

  const showAutoCacheOnboarding = useCallback(() => {
    if (offlineToastShownRef.shown) return
    offlineToastShownRef.shown = true
    markAutoCacheOnboardingShown()
    showIsland({
      kind: 'toast',
      title: t('offline.autoCacheIntro.title', {
        defaultValue:
          'Лайкнутые треки сохраняются для оффлайна',
      }),
      hint: t('offline.autoCacheIntro.disable', {
        defaultValue:
          'Нажмите, чтобы отключить',
      }),
      onClick: () => setAutoCacheEnabled(false),
      durationMs: 7000,
    })
  }, [t, offlineToastShownRef])

  const isLiked = useCallback(
    (trackId: number) => likedIds.has(trackId),
    [likedIds],
  )

  const isDisliked = useCallback(
    (trackId: number) => dislikedIds.has(trackId),
    [dislikedIds],
  )

  const toggleLike = useCallback(async (
    trackId: number,
    trackHint?: Track,
  ) => {
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
      if (liked && getAutoCacheEnabled()) {
        queueAutoCache(trackHint ?? trackId, {
          onFirstSuccess: showAutoCacheOnboarding,
        })
      } else if (!liked) {
        cancelAutoCache(trackId)
        void removeOfflineTrack(trackId)
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
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(
          e,
          t('redesign.likesErrors.likeFail'),
        ),
        durationMs: 3500,
      })
    }
  }, [likedIds, dislikedIds, t, showAutoCacheOnboarding])

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
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(
          e,
          t('redesign.likesErrors.dislikeFail'),
        ),
        durationMs: 3500,
      })
    }
  }, [likedIds, dislikedIds, t])

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
