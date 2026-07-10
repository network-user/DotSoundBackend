import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
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
  getCachedIdsSync,
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

  const catchUpRanRef = useRef(false)

  // FB-2: track the latest in-flight toggle per track id (shared by
  // like and dislike, since both mutate the same track). Only the
  // newest action for a given id applies its server result or rolls
  // back — an older, superseded request becomes a no-op, and a rollback
  // touches only its own track, never the whole set. This prevents a
  // failed toggle from wiping concurrent likes/dislikes of other tracks.
  const toggleSeqRef = useRef(0)
  const inFlightToggleRef = useRef<Map<number, number>>(new Map())

  useEffect(() => {
    const uid = getUserId()
    if (!uid) return
    void (async () => {
      const [likesRes, disRes] = await Promise.allSettled([
        api.getLikedTracks(uid, 1, 200),
        api.getDislikedTracks(uid, 1, 200),
      ])
      if (disRes.status === 'fulfilled') {
        setDislikedIds(
          new Set(disRes.value.items.map((t) => t.id)),
        )
      }
      if (likesRes.status !== 'fulfilled') return
      const data = likesRes.value
      setLikedIds(new Set(data.items.map((t) => t.id)))
      if (
        !isOfflineCacheSupported() ||
        !getAutoCacheEnabled() ||
        catchUpRanRef.current
      )
        return
      catchUpRanRef.current = true
      await ensureCachedIdsLoaded()
      const cached = getCachedIdsSync()
      const pending = data.items.filter(
        (tr) =>
          tr.access_mode === 'internal_stream' &&
          !cached.has(tr.id),
      )
      if (pending.length === 0) return
      const idle =
        (
          window as unknown as {
            requestIdleCallback?: (
              cb: () => void,
              opts?: { timeout?: number },
            ) => number
          }
        ).requestIdleCallback ??
        ((cb: () => void) => window.setTimeout(cb, 2000))
      idle(() => {
        for (const tr of pending.slice(0, 5)) {
          queueAutoCache(tr, {
            onFirstSuccess: showAutoCacheOnboarding,
          })
        }
      })
    })()
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

    // Snapshot only THIS track's prior membership (per-item), never the
    // whole set, so a rollback can't wipe concurrent toggles of others.
    const prevLikedHas = likedIds.has(trackId)
    const prevDislikedHas = dislikedIds.has(trackId)
    const willLike = !prevLikedHas

    // Claim latest-action ownership for this track id.
    const token = ++toggleSeqRef.current
    inFlightToggleRef.current.set(trackId, token)
    const isCurrent = () =>
      inFlightToggleRef.current.get(trackId) === token
    const clearIfCurrent = () => {
      if (isCurrent()) inFlightToggleRef.current.delete(trackId)
    }

    setLikedIds((prev) => _withIds(prev, [trackId], willLike))
    if (willLike) {
      setDislikedIds((prev) => _withIds(prev, [trackId], false))
    }

    try {
      const { liked, playback_variant_track_ids } =
        await api.toggleLike(uid, trackId)
      // A newer toggle of this track superseded us: drop our result.
      if (!isCurrent()) return
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
      clearIfCurrent()
    } catch (e) {
      if (_isNetworkError(e)) {
        // Superseded by a newer toggle of this track: skip the offline
        // enqueue, or a stale replay would later flip the like back.
        // Symmetric with the success/rollback latest-action guards.
        if (!isCurrent()) return
        clearIfCurrent()
        await queueMutation(
          'POST',
          `/api/v1/likes/${uid}/${trackId}`,
        )
        return
      }
      // Superseded by a newer action: leave its optimistic state alone.
      if (!isCurrent()) return
      // Per-item rollback: revert ONLY this track to its prior value.
      setLikedIds((prev) => _withIds(prev, [trackId], prevLikedHas))
      if (willLike) {
        setDislikedIds((prev) =>
          _withIds(prev, [trackId], prevDislikedHas),
        )
      }
      clearIfCurrent()
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

    const prevLikedHas = likedIds.has(trackId)
    const prevDislikedHas = dislikedIds.has(trackId)
    const willDislike = !prevDislikedHas

    const token = ++toggleSeqRef.current
    inFlightToggleRef.current.set(trackId, token)
    const isCurrent = () =>
      inFlightToggleRef.current.get(trackId) === token
    const clearIfCurrent = () => {
      if (isCurrent()) inFlightToggleRef.current.delete(trackId)
    }

    setDislikedIds((prev) => _withIds(prev, [trackId], willDislike))
    if (willDislike) {
      setLikedIds((prev) => _withIds(prev, [trackId], false))
    }

    try {
      const { disliked, playback_variant_track_ids } =
        await api.toggleDislike(uid, trackId)
      if (!isCurrent()) return
      const ids =
        playback_variant_track_ids.length > 0
          ? playback_variant_track_ids
          : [trackId]
      setDislikedIds((prev) => _withIds(prev, ids, disliked))
      if (disliked) {
        setLikedIds((prev) => _withIds(prev, ids, false))
      }
      clearIfCurrent()
    } catch (e) {
      if (_isNetworkError(e)) {
        // Superseded by a newer toggle of this track: skip the offline
        // enqueue, or a stale replay would later flip the dislike back.
        // Symmetric with the success/rollback latest-action guards.
        if (!isCurrent()) return
        clearIfCurrent()
        await queueMutation(
          'POST',
          `/api/v1/dislikes/${uid}/${trackId}`,
        )
        return
      }
      if (!isCurrent()) return
      // Per-item rollback: revert ONLY this track to its prior value.
      setDislikedIds((prev) =>
        _withIds(prev, [trackId], prevDislikedHas),
      )
      if (willDislike) {
        setLikedIds((prev) => _withIds(prev, [trackId], prevLikedHas))
      }
      clearIfCurrent()
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
