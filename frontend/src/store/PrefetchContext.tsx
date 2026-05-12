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
import { api } from '@/lib/api'
import {
  getPrefetchManager,
  type PrefetchManager,
} from '@/lib/prefetch/PrefetchManager'
import type {
  PrefetchContextName,
  PrefetchEnqueueOptions,
  PrefetchInputTrack,
  PrefetchPolicySnapshot,
} from '@/lib/prefetch/types'

interface PrefetchContextValue {
  manager: PrefetchManager
  policy: PrefetchPolicySnapshot
  enabled: boolean
  setEnabled: (value: boolean) => void
  prefetch: (
    tracks: PrefetchInputTrack[],
    options: PrefetchEnqueueOptions,
  ) => Promise<number>
  cancelContext: (context: PrefetchContextName) => void
}

const PrefetchCtx = createContext<PrefetchContextValue | null>(null)

const SMART_BUFFERING_FLAG = 'setting-smart-buffering'

function _readEnabled(): boolean {
  try {
    const raw = window.localStorage.getItem(SMART_BUFFERING_FLAG)
    return raw !== 'false'
  } catch {
    return true
  }
}

export function PrefetchProvider({
  children,
}: {
  children: ReactNode
}) {
  const managerRef = useRef<PrefetchManager>(getPrefetchManager())
  const [policy, setPolicy] = useState<PrefetchPolicySnapshot>(
    () => managerRef.current.getPolicy(),
  )
  const [enabled, setEnabledState] = useState<boolean>(() =>
    _readEnabled(),
  )

  useEffect(() => {
    const m = managerRef.current
    m.configurePolicyFetcher(
      async ({ network, quotaBytes }) => {
        try {
          const remote = await api.getPrefetchPolicy({
            effective_type: network.effectiveType ?? undefined,
            save_data: network.saveData,
            downlink: network.downlinkMbps ?? undefined,
            quota_bytes:
              typeof quotaBytes === 'number' && quotaBytes > 0
                ? quotaBytes
                : undefined,
          })
          const next: PrefetchPolicySnapshot = {
            enabled: remote.enabled,
            algorithmVersion: remote.algorithm_version,
            hotPoolSize: remote.hot_pool_size,
            warmSegmentsPerTrack: remote.warm_segments_per_track,
            initialBytesPerTrack: remote.initial_bytes_per_track,
            maxStorageBytes: remote.max_storage_bytes,
            inMemoryTtlSeconds: remote.in_memory_ttl_seconds,
            persistentTtlSeconds: remote.persistent_ttl_seconds,
            evictionPolicy: 'lru',
            concurrentPrefetchLimit:
              remote.concurrent_prefetch_limit,
            skipThirdPartyAudioCache:
              remote.skip_third_party_audio_cache,
            lookaheadByContext:
              remote.lookahead_by_context as PrefetchPolicySnapshot['lookaheadByContext'],
            fullDownloadAhead: remote.full_download_ahead,
          }
          setPolicy(next)
          return next
        } catch {
          return null
        }
      },
    )
    void m.start()
    return () => {
      m.stop()
    }
  }, [])

  const setEnabled = useCallback((value: boolean) => {
    setEnabledState(value)
    managerRef.current.setUserEnabled(value)
    if (!value) {
      managerRef.current.cancelAll()
    }
  }, [])

  const prefetch = useCallback(
    async (
      tracks: PrefetchInputTrack[],
      options: PrefetchEnqueueOptions,
    ) => {
      if (!enabled) return 0
      return managerRef.current.enqueue(tracks, options)
    },
    [enabled],
  )

  const cancelContext = useCallback(
    (context: PrefetchContextName) => {
      managerRef.current.cancelContext(context)
    },
    [],
  )

  const value = useMemo<PrefetchContextValue>(
    () => ({
      manager: managerRef.current,
      policy,
      enabled,
      setEnabled,
      prefetch,
      cancelContext,
    }),
    [policy, enabled, setEnabled, prefetch, cancelContext],
  )

  return (
    <PrefetchCtx.Provider value={value}>
      {children}
    </PrefetchCtx.Provider>
  )
}

export function usePrefetch(): PrefetchContextValue {
  const ctx = useContext(PrefetchCtx)
  if (!ctx) {
    throw new Error(
      'usePrefetch must be used within PrefetchProvider',
    )
  }
  return ctx
}

/**
 * Light-weight, no-throw variant for components that may render
 * outside the provider tree (e.g. admin shell). Returns ``null``
 * silently instead of crashing.
 */
export function useOptionalPrefetch(): PrefetchContextValue | null {
  return useContext(PrefetchCtx)
}

/**
 * Convenience: prefetch a static list of tracks every time the
 * list identity changes for the given context. Pass ``null`` /
 * empty arrays freely; the hook bails out without scheduling.
 *
 * - ``replaceContext`` is ``true`` by default: a fresh list for the
 *   same context cancels the previous warm-set. This is the right
 *   default for view-level contexts (Home, Playlist, etc.).
 * - For "fan-in" contexts where many components contribute one or
 *   two tracks each (e.g. ``chat_shared``) pass ``additive: true``
 *   so siblings do not stomp on each other.
 * - We deliberately do NOT cancel the context on unmount: that is
 *   what made many small components (chat bubbles, virtualised
 *   lists) cancel work scheduled by their siblings.
 */
export function usePrefetchTracks(
  tracks: PrefetchInputTrack[] | null | undefined,
  context: PrefetchContextName,
  options?: {
    lookaheadOverride?: number
    enabled?: boolean
    additive?: boolean
  },
): void {
  const ctx = useOptionalPrefetch()
  const enabledFlag = options?.enabled ?? true
  const lookaheadOverride = options?.lookaheadOverride
  const additive = options?.additive ?? false
  const idKey = useMemo(
    () => (tracks ?? []).map((t) => t.id).join(','),
    [tracks],
  )
  useEffect(() => {
    if (!ctx || !enabledFlag) return
    if (!tracks || tracks.length === 0) return
    void ctx.prefetch(tracks, {
      context,
      replaceContext: !additive,
      lookaheadOverride,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx, enabledFlag, context, lookaheadOverride, additive, idKey])
}
