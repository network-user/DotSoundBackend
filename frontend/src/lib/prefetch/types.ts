import type { Track } from '@/types/api'

export type PrefetchContextName =
  | 'home'
  | 'album'
  | 'artist'
  | 'playlist'
  | 'genre_mix'
  | 'daily_mix'
  | 'weekly_mix'
  | 'weekly_top'
  | 'user_choice'
  | 'radio'
  | 'queue'
  | 'playback'
  | 'search_results'
  | 'similar_in_card'
  | 'chat_shared'
  | 'deep_link'
  | 'continue_on_app_start'
  | 'library'

export interface PrefetchPolicySnapshot {
  enabled: boolean
  algorithmVersion: string
  hotPoolSize: number
  warmSegmentsPerTrack: number
  initialBytesPerTrack: number
  maxStorageBytes: number
  inMemoryTtlSeconds: number
  persistentTtlSeconds: number
  evictionPolicy: 'lru'
  concurrentPrefetchLimit: number
  skipThirdPartyAudioCache: boolean
  lookaheadByContext: Partial<Record<PrefetchContextName, number>>
}

export interface PrefetchTrackBrief {
  id: number
  is_public?: boolean
  access_mode?: string
  source_platform?: string | null
  hls_manifest_key?: string | null
}

export type PrefetchInputTrack =
  | Track
  | PrefetchTrackBrief

export interface PrefetchEnqueueOptions {
  context: PrefetchContextName
  /** Optional override: explicit number of tracks to warm up. */
  lookaheadOverride?: number
  /** Cancel the previous warm-set for this context first. */
  replaceContext?: boolean
}

export interface PrefetchStats {
  warmed: number
  evicted: number
  hits: number
  misses: number
  overBudget: number
  bytesUsed: number
}

export interface PrefetchManagerStatus {
  policy: PrefetchPolicySnapshot
  cachedHlsManifestTrackIds: number[]
  warmedTrackIds: number[]
  policySource: 'default' | 'remote'
  stats: PrefetchStats
}

export const DEFAULT_PREFETCH_POLICY: PrefetchPolicySnapshot = {
  enabled: true,
  algorithmVersion: 'local.default',
  hotPoolSize: 1,
  warmSegmentsPerTrack: 2,
  initialBytesPerTrack: 256 * 1024,
  maxStorageBytes: 32 * 1024 * 1024,
  inMemoryTtlSeconds: 5 * 60,
  persistentTtlSeconds: 24 * 60 * 60,
  evictionPolicy: 'lru',
  concurrentPrefetchLimit: 3,
  skipThirdPartyAudioCache: true,
  lookaheadByContext: {
    home: 3,
    album: 5,
    artist: 3,
    playlist: 5,
    genre_mix: 3,
    daily_mix: 3,
    weekly_mix: 3,
    weekly_top: 3,
    user_choice: 3,
    radio: 3,
    queue: 3,
    playback: 3,
    search_results: 3,
    similar_in_card: 2,
    chat_shared: 1,
    deep_link: 1,
    continue_on_app_start: 1,
    library: 3,
  },
}
