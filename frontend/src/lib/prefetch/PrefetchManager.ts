/**
 * Smart predictive audio buffering for the .sound Mini App.
 *
 * Responsibilities:
 * - Pull the live policy snapshot from PrivateCore (via Backend
 *   ``GET /api/v1/prefetch/policy``) and respect its lookahead /
 *   storage budget / network-aware degradation rules.
 * - Maintain a priority queue of upcoming tracks per trigger
 *   context (home, album, artist, radio, queue, playback, ...).
 * - Warm two layers per track: HLS master/variant manifests + the
 *   first ``warm_segments_per_track`` ``.ts`` segments. The Service
 *   Worker (via ``vite-plugin-pwa`` runtimeCaching) makes the warm
 *   bytes visible to the actual ``<audio>`` element transparently.
 * - Skip third-party stream platforms whose CDN URLs expire fast
 *   (SoundCloud, YouTube, Bandcamp).
 * - Persist a per-track LRU index in IndexedDB so a fresh session
 *   can prefer warm tracks for the next radio fetch.
 */

import {
  DEFAULT_PREFETCH_POLICY,
  type PrefetchContextName,
  type PrefetchEnqueueOptions,
  type PrefetchInputTrack,
  type PrefetchManagerStatus,
  type PrefetchPolicySnapshot,
} from './types'
import {
  readNetworkSnapshot,
  subscribeToNetworkChanges,
  type NetworkSnapshot,
} from './network'
import {
  dropWarmRecord,
  getStorageQuota,
  listWarmRecords,
  persistWarmRecord,
} from './storage'

const SMART_BUFFERING_FLAG = 'setting-smart-buffering'

interface PendingTask {
  trackId: number
  context: PrefetchContextName
  hlsManifestUrl: string | null
  progressiveUrl: string | null
  segmentDirUrls: string[]
  sourcePlatform: string | null
  serverWarmOnly: boolean
  abort: AbortController
}

interface FetchPolicyArgs {
  network: NetworkSnapshot
  quotaBytes: number | null
}

const POLICY_REFRESH_MS = 5 * 60 * 1000

const SEGMENT_VARIANT_PREFERENCE = ['lo', 'hi'] as const

const HOT_TTL_MS_FALLBACK = DEFAULT_PREFETCH_POLICY.inMemoryTtlSeconds * 1000

const HOT_TIMESTAMPS_HARD_CAP = 256

type FetchPriority = 'low' | 'high' | 'auto'

interface FetchInitWithPriority extends RequestInit {
  priority?: FetchPriority
}

function _isThirdPartyCacheableSafe(track: PrefetchInputTrack): boolean {
  const accessMode = (track as { access_mode?: string }).access_mode
  if (accessMode === 'third_party_stream') return false
  return true
}

function _trackHlsManifestUrl(track: PrefetchInputTrack): string | null {
  const isPublic = (track as { is_public?: boolean }).is_public ?? true
  if (!isPublic) return null
  if (!_isThirdPartyCacheableSafe(track)) return null
  return `/api/v1/tracks/${track.id}/hls/master.m3u8`
}

function _trackProgressiveUrl(track: PrefetchInputTrack): string | null {
  if (!_isThirdPartyCacheableSafe(track)) return null
  return `/api/v1/tracks/${track.id}/audio?force_progressive=true`
}

function _firstNSegmentLines(manifestText: string, n: number): string[] {
  const lines = manifestText
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith('#'))
  return lines.slice(0, n)
}

function _resolveVariantUrl(
  trackId: number,
  variant: string,
): string {
  return `/api/v1/tracks/${trackId}/hls/${variant}/playlist.m3u8`
}

function _resolveSegmentUrl(
  trackId: number,
  variant: string,
  fileName: string,
): string {
  return `/api/v1/tracks/${trackId}/hls/${variant}/${fileName}`
}

class FifoSemaphore {
  private inFlight = 0
  private waiting: Array<() => void> = []
  constructor(private limit: number) {}

  setLimit(value: number): void {
    this.limit = Math.max(1, Math.floor(value))
    while (this.inFlight < this.limit && this.waiting.length > 0) {
      const next = this.waiting.shift()
      if (next) next()
    }
  }

  async acquire(): Promise<() => void> {
    if (this.inFlight < this.limit) {
      this.inFlight += 1
      return () => this._release()
    }
    return new Promise<() => void>((resolve) => {
      this.waiting.push(() => {
        this.inFlight += 1
        resolve(() => this._release())
      })
    })
  }

  private _release(): void {
    this.inFlight -= 1
    const next = this.waiting.shift()
    if (next) next()
  }
}

export class PrefetchManager {
  private policy: PrefetchPolicySnapshot = DEFAULT_PREFETCH_POLICY
  private policySource: 'default' | 'remote' = 'default'
  private policyAt = 0
  private semaphore = new FifoSemaphore(
    DEFAULT_PREFETCH_POLICY.concurrentPrefetchLimit,
  )
  private warmTrackIds = new Set<number>()
  private cachedManifestTrackIds = new Set<number>()
  private inFlightTrackIds = new Set<number>()
  private contextTasks = new Map<
    PrefetchContextName,
    PendingTask[]
  >()
  private hotTimestamps = new Map<number, number>()
  private fetcher: (
    args: FetchPolicyArgs,
  ) => Promise<PrefetchPolicySnapshot | null> = async () => null
  private boundNetworkListener: (() => void) | null = null

  configurePolicyFetcher(
    fetcher: (
      args: FetchPolicyArgs,
    ) => Promise<PrefetchPolicySnapshot | null>,
  ): void {
    this.fetcher = fetcher
  }

  isEnabled(): boolean {
    if (typeof window === 'undefined') return false
    if (!this.policy.enabled) return false
    try {
      const raw = window.localStorage.getItem(SMART_BUFFERING_FLAG)
      if (raw === 'false') return false
    } catch {
      /* ignore */
    }
    return true
  }

  setUserEnabled(value: boolean): void {
    try {
      window.localStorage.setItem(
        SMART_BUFFERING_FLAG,
        value ? 'true' : 'false',
      )
    } catch {
      /* ignore */
    }
    if (!value) {
      this.cancelAll()
    }
  }

  async start(): Promise<void> {
    if (this.boundNetworkListener) return
    await this._refreshPolicy()
    this.boundNetworkListener = subscribeToNetworkChanges(() => {
      void this._refreshPolicy(true)
    })
    void this._hydrateWarmIndex()
  }

  stop(): void {
    if (this.boundNetworkListener) {
      this.boundNetworkListener()
      this.boundNetworkListener = null
    }
    this.cancelAll()
  }

  getPolicy(): PrefetchPolicySnapshot {
    return this.policy
  }

  status(): PrefetchManagerStatus {
    return {
      policy: this.policy,
      cachedHlsManifestTrackIds: Array.from(this.cachedManifestTrackIds),
      warmedTrackIds: Array.from(this.warmTrackIds),
      policySource: this.policySource,
    }
  }

  cancelAll(): void {
    for (const tasks of this.contextTasks.values()) {
      for (const task of tasks) {
        try {
          task.abort.abort()
        } catch {
          /* ignore */
        }
      }
    }
    this.contextTasks.clear()
  }

  cancelContext(context: PrefetchContextName): void {
    const tasks = this.contextTasks.get(context)
    if (!tasks) return
    for (const task of tasks) {
      try {
        task.abort.abort()
      } catch {
        /* ignore */
      }
    }
    this.contextTasks.delete(context)
  }

  /**
   * Enqueue prefetch for the given tracks. Returns the actual count
   * scheduled (after lookahead truncation, dedupe, and policy gates).
   */
  async enqueue(
    tracks: PrefetchInputTrack[],
    options: PrefetchEnqueueOptions,
  ): Promise<number> {
    if (!this.isEnabled()) return 0
    if (tracks.length === 0) return 0

    if (Date.now() - this.policyAt > POLICY_REFRESH_MS) {
      void this._refreshPolicy(false)
    }

    if (options.replaceContext) {
      this.cancelContext(options.context)
    }

    const lookahead = this._resolveLookahead(
      options.context,
      options.lookaheadOverride,
    )
    if (lookahead <= 0) return 0

    const eligible: PrefetchInputTrack[] = []
    for (const track of tracks) {
      if (eligible.length >= lookahead) break
      if (!track || typeof track.id !== 'number') continue
      if (this.warmTrackIds.has(track.id)) {
        this._touchHot(track.id)
        continue
      }
      if (this.inFlightTrackIds.has(track.id)) {
        continue
      }
      const accessMode = (track as { access_mode?: string }).access_mode
      if (
        accessMode === 'third_party_stream' &&
        this.policy.skipThirdPartyAudioCache
      ) {
        eligible.push(track)
        continue
      }
      if (
        this.policy.skipThirdPartyAudioCache &&
        !_isThirdPartyCacheableSafe(track)
      ) {
        continue
      }
      eligible.push(track)
    }
    if (eligible.length === 0) return 0

    const list = this.contextTasks.get(options.context) ?? []
    let scheduled = 0
    for (const track of eligible) {
      const abort = new AbortController()
      const serverWarmOnly =
        (track as { access_mode?: string }).access_mode ===
          'third_party_stream' &&
        this.policy.skipThirdPartyAudioCache
      const task: PendingTask = {
        trackId: track.id,
        context: options.context,
        hlsManifestUrl: serverWarmOnly
          ? null
          : _trackHlsManifestUrl(track),
        progressiveUrl: serverWarmOnly
          ? null
          : _trackProgressiveUrl(track),
        segmentDirUrls: [],
        sourcePlatform:
          (track as { source_platform?: string | null }).source_platform ??
          null,
        serverWarmOnly,
        abort,
      }
      list.push(task)
      this.inFlightTrackIds.add(track.id)
      scheduled += 1
      void this._runTask(task)
    }
    this.contextTasks.set(options.context, list)
    return scheduled
  }

  private _resolveLookahead(
    context: PrefetchContextName,
    override: number | undefined,
  ): number {
    if (typeof override === 'number' && override >= 0) {
      return Math.min(
        override,
        this.policy.lookaheadByContext[context] ??
          DEFAULT_PREFETCH_POLICY.lookaheadByContext[context] ??
          0,
      )
    }
    return this.policy.lookaheadByContext[context] ?? 0
  }

  private _touchHot(trackId: number): void {
    this.hotTimestamps.set(trackId, Date.now())
    if (this.hotTimestamps.size > HOT_TIMESTAMPS_HARD_CAP) {
      const firstKey = this.hotTimestamps.keys().next().value
      if (typeof firstKey === 'number') {
        this.hotTimestamps.delete(firstKey)
      }
    }
  }

  private _evictExpiredHot(): void {
    const ttlMs =
      this.policy.inMemoryTtlSeconds > 0
        ? this.policy.inMemoryTtlSeconds * 1000
        : HOT_TTL_MS_FALLBACK
    const now = Date.now()
    for (const [id, ts] of this.hotTimestamps.entries()) {
      if (now - ts > ttlMs) {
        this.hotTimestamps.delete(id)
      }
    }
  }

  private async _runTask(task: PendingTask): Promise<void> {
    const release = await this.semaphore.acquire()
    let warmed = false
    try {
      if (task.abort.signal.aborted) return
      if (task.serverWarmOnly) {
        await this._warmThirdPartyServerCache(task)
        return
      }
      if (task.hlsManifestUrl) {
        warmed = await this._warmHls(task)
      } else if (task.progressiveUrl) {
        warmed = await this._warmProgressivePrefix(task)
      }
      if (warmed) {
        this.warmTrackIds.add(task.trackId)
        this._touchHot(task.trackId)
        await persistWarmRecord({
          trackId: task.trackId,
          warmedAt: Date.now(),
          context: task.context,
          bytes: 0,
          sourcePlatform: task.sourcePlatform,
        })
      }
    } catch {
      /* swallow individual task failures */
    } finally {
      this.inFlightTrackIds.delete(task.trackId)
      this._evictExpiredHot()
      release()
      this._removePending(task)
    }
  }

  private async _warmThirdPartyServerCache(
    task: PendingTask,
  ): Promise<void> {
    try {
      const { api } = await import('@/lib/api')
      await api.warmTrackStreamCache([task.trackId])
      this.warmTrackIds.add(task.trackId)
      this._touchHot(task.trackId)
      await persistWarmRecord({
        trackId: task.trackId,
        warmedAt: Date.now(),
        context: task.context,
        bytes: 0,
        sourcePlatform: task.sourcePlatform,
      })
    } catch {
      /* ignore */
    }
  }

  private _removePending(task: PendingTask): void {
    const tasks = this.contextTasks.get(task.context)
    if (!tasks) return
    const next = tasks.filter((t) => t !== task)
    if (next.length === 0) {
      this.contextTasks.delete(task.context)
    } else {
      this.contextTasks.set(task.context, next)
    }
  }

  private async _warmHls(task: PendingTask): Promise<boolean> {
    if (!task.hlsManifestUrl) return false
    if (task.abort.signal.aborted) return false
    const masterRes = await this._safeFetch(
      task.hlsManifestUrl,
      task.abort.signal,
    )
    if (!masterRes) return false
    const masterText = await masterRes.text().catch(() => '')
    if (!masterText) return false
    this.cachedManifestTrackIds.add(task.trackId)

    const variant = this._pickVariant(masterText)
    if (!variant) return true

    if (task.abort.signal.aborted) return true
    const variantUrl = _resolveVariantUrl(task.trackId, variant)
    const variantRes = await this._safeFetch(variantUrl, task.abort.signal)
    if (!variantRes) return true
    const variantText = await variantRes.text().catch(() => '')
    if (!variantText) return true

    const segCount = Math.max(1, this.policy.warmSegmentsPerTrack)
    const segments = _firstNSegmentLines(variantText, segCount)
    for (const segment of segments) {
      if (task.abort.signal.aborted) break
      const segUrl = _resolveSegmentUrl(
        task.trackId,
        variant,
        segment,
      )
      const segRes = await this._safeFetch(segUrl, task.abort.signal)
      if (!segRes) continue
      try {
        await segRes.body?.cancel()
      } catch {
        /* ignore */
      }
    }
    return true
  }

  private _pickVariant(masterText: string): string | null {
    for (const v of SEGMENT_VARIANT_PREFERENCE) {
      if (masterText.includes(`${v}/playlist.m3u8`)) return v
    }
    return SEGMENT_VARIANT_PREFERENCE[0]
  }

  private async _warmProgressivePrefix(
    task: PendingTask,
  ): Promise<boolean> {
    if (!task.progressiveUrl) return false
    if (task.abort.signal.aborted) return false
    const initBytes = Math.max(0, this.policy.initialBytesPerTrack)
    if (initBytes <= 0) return false
    const headers = new Headers()
    headers.set('Range', `bytes=0-${initBytes - 1}`)
    const res = await this._safeFetch(
      task.progressiveUrl,
      task.abort.signal,
      headers,
    )
    if (!res) return false
    try {
      await res.body?.cancel()
    } catch {
      /* ignore */
    }
    return true
  }

  private async _safeFetch(
    url: string,
    signal: AbortSignal,
    headers?: Headers,
  ): Promise<Response | null> {
    try {
      const init: FetchInitWithPriority = {
        signal,
        credentials: 'include',
        cache: 'default',
        headers,
        priority: 'low',
      }
      const res = await fetch(url, init)
      if (!res.ok && res.status !== 206) return null
      return res
    } catch {
      return null
    }
  }

  private async _refreshPolicy(force = false): Promise<void> {
    if (!force && Date.now() - this.policyAt < POLICY_REFRESH_MS) {
      return
    }
    const network = readNetworkSnapshot()
    const { quota } = await getStorageQuota()
    try {
      const remote = await this.fetcher({
        network,
        quotaBytes: quota,
      })
      if (remote) {
        this.policy = remote
        this.policySource = 'remote'
      } else if (this.policySource === 'default') {
        this.policy = DEFAULT_PREFETCH_POLICY
      }
    } catch {
      /* keep current policy on error */
    }
    this.policyAt = Date.now()
    this.semaphore.setLimit(this.policy.concurrentPrefetchLimit || 1)
  }

  private async _hydrateWarmIndex(): Promise<void> {
    const records = await listWarmRecords()
    const cutoff =
      Date.now() - this.policy.persistentTtlSeconds * 1000
    const drops: Promise<void>[] = []
    for (const rec of records) {
      if (rec.warmedAt < cutoff) {
        drops.push(dropWarmRecord(rec.trackId))
        continue
      }
      this.warmTrackIds.add(rec.trackId)
    }
    if (drops.length > 0) {
      await Promise.all(drops)
    }
  }
}

let _singleton: PrefetchManager | null = null

export function getPrefetchManager(): PrefetchManager {
  if (!_singleton) {
    _singleton = new PrefetchManager()
  }
  return _singleton
}
