import { useAdminAuth } from '../store/adminAuthStore'
import { ensureCsrf, readCsrfCookie } from './csrf'
import { getAdminApiBasePath } from '@/lib/adminPath'
import type { PlaybackRepairSummary } from '../components/widgets/PlaybackRepairSummaryPanel'

export interface LyricsTimecodeSyncJob {
  id: string
  track_id: number
  track_title: string | null
  track_artist: string | null
  status: string
  profile: string
  queue_priority: number
  current_tier: string | null
  error: string | null
  attempts: number
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  progress_id: string | null
  request_with_sync: boolean
}

function normalizeHttpDetail(raw: unknown): string {
  if (typeof raw === 'string') {
    return raw
  }
  if (raw === null || raw === undefined) {
    return ''
  }
  if (
    typeof raw === 'number' ||
    typeof raw === 'boolean'
  ) {
    return String(raw)
  }
  if (Array.isArray(raw)) {
    const parts = raw.map((item) => {
      if (
        item &&
        typeof item === 'object' &&
        'msg' in item
      ) {
        return String(
          (item as { msg?: unknown }).msg ?? '',
        )
      }
      if (typeof item === 'string') {
        return item
      }
      try {
        return JSON.stringify(item)
      } catch {
        return ''
      }
    })
    return parts.filter(Boolean).join('; ')
  }
  if (typeof raw === 'object') {
    try {
      return JSON.stringify(raw)
    } catch {
      return ''
    }
  }
  return String(raw)
}

export class AdminApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: unknown) {
    const message =
      normalizeHttpDetail(detail) ||
      `HTTP ${status}`
    super(message)
    this.status = status
    this.detail = message
  }
}

export interface SoundCloudDiagnoseResponse {
  request: {
    url: string
    egress: {
      outbound_configured: boolean
      proxied: boolean
      proxy_url: string | null
      proxy_scheme: string | null
      proxy_host: string | null
      proxy_port: number | null
      ip_probe: {
        ok: boolean
        ip?: string | null
        provider: string
        status_code?: number
        error?: string
      }
    }
  }
  decision: {
    allowed: boolean
    reason: string | null
    user_message: string | null
    diagnostic: Record<string, unknown>
  }
  playback?: {
    mode: 'dotsound_stream' | 'unavailable'
    label: string
    reason: string | null
  }
  track: Record<string, unknown>
  manifest_probes: Array<Record<string, unknown>>
  track_authorization_present: boolean
}

interface RequestOptions {
  method?: string
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  headers?: Record<string, string>
  signal?: AbortSignal
  isUserToken?: boolean
}

function buildUrl(
  path: string,
  query?: RequestOptions['query'],
): string {
  const base = getAdminApiBasePath()
  const url = new URL(
    `${base}${path}`,
    window.location.origin,
  )
  if (query) {
    for (const [key, value] of Object.entries(
      query,
    )) {
      if (value === undefined || value === null)
        continue
      url.searchParams.set(key, String(value))
    }
  }
  return url.pathname + url.search
}

let userTokenProvider: () => string | null =
  () => null

export function setUserTokenProvider(
  fn: () => string | null,
): void {
  userTokenProvider = fn
}

function readDsCsrfCookie(): string {
  if (typeof document === 'undefined') return ''
  const match = document.cookie.match(
    /(?:^|;\s*)ds_csrf=([^;]+)/,
  )
  return match ? decodeURIComponent(match[1]) : ''
}

async function rawRequest(
  path: string,
  opts: RequestOptions,
): Promise<Response> {
  const method = (opts.method || 'GET').toUpperCase()
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(opts.headers || {}),
  }
  const isForm = opts.body instanceof FormData
  if (opts.body !== undefined && !isForm) {
    headers['Content-Type'] = 'application/json'
  }
  if (
    method !== 'GET' &&
    method !== 'HEAD' &&
    method !== 'OPTIONS'
  ) {
    const csrf = await ensureCsrf()
    if (csrf) headers['X-Admin-CSRF'] = csrf
    if (!headers['X-CSRF-Token']) {
      const dsCsrf = readDsCsrfCookie()
      if (dsCsrf) {
        headers['X-CSRF-Token'] = dsCsrf
      }
    }
  }
  if (opts.isUserToken) {
    const userToken = userTokenProvider()
    if (userToken) {
      headers['Authorization'] = `Bearer ${userToken}`
    }
  } else {
    const adminToken =
      useAdminAuth.getState().accessToken
    if (adminToken) {
      headers['Authorization'] = `Bearer ${adminToken}`
    }
  }
  const url = buildUrl(path, opts.query)
  return fetch(url, {
    method,
    headers,
    credentials: 'include',
    body:
      opts.body === undefined
        ? undefined
        : isForm
          ? (opts.body as FormData)
          : JSON.stringify(opts.body),
    signal: opts.signal,
  })
}

const PROACTIVE_REFRESH_THRESHOLD_MS = 30_000
let inflightRefresh: Promise<boolean> | null = null

function loggedOutKeepAdmin(): void {
  const store = useAdminAuth.getState()
  store.setStatus('needs_login')
  // wipe token state but keep status as 'needs_login'
  // so user is not bumped to the unauth wall
  useAdminAuth.setState({
    accessToken: null,
    expiresAt: null,
    capabilities: [],
  })
}

interface RefreshResult {
  access_token: string
  refresh_token: string
  expires_in: number
}

let inflightRefreshDetailed:
  | Promise<RefreshResult | null>
  | null = null

async function tryRefreshDetailed(): Promise<
  RefreshResult | null
> {
  if (inflightRefreshDetailed) {
    return inflightRefreshDetailed
  }
  inflightRefreshDetailed = (async () => {
    try {
      const refreshed = await rawRequest(
        '/auth/refresh',
        { method: 'POST' },
      )
      if (refreshed.status !== 200) {
        loggedOutKeepAdmin()
        return null
      }
      const data =
        (await refreshed.json()) as RefreshResult
      useAdminAuth
        .getState()
        .setSession(
          data.access_token,
          data.expires_in,
        )
      return data
    } catch {
      loggedOutKeepAdmin()
      return null
    } finally {
      inflightRefreshDetailed = null
    }
  })()
  return inflightRefreshDetailed
}

async function tryRefresh(): Promise<boolean> {
  if (inflightRefresh) {
    return inflightRefresh
  }
  inflightRefresh = (async () => {
    const result = await tryRefreshDetailed()
    return result !== null
  })()
  try {
    return await inflightRefresh
  } finally {
    inflightRefresh = null
  }
}

async function withRefresh(
  doRequest: () => Promise<Response>,
  opts: RequestOptions,
): Promise<Response> {
  if (!opts.isUserToken) {
    const state = useAdminAuth.getState()
    if (
      state.accessToken &&
      state.expiresAt &&
      state.expiresAt - Date.now() <
        PROACTIVE_REFRESH_THRESHOLD_MS
    ) {
      await tryRefresh()
    }
  }

  const response = await doRequest()
  if (response.status !== 401) {
    return response
  }
  if (
    !opts.isUserToken &&
    useAdminAuth.getState().accessToken === null
  ) {
    return response
  }
  const ok = await tryRefresh()
  if (!ok) {
    return response
  }
  return doRequest()
}

export async function adminFetch<T = unknown>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const response = await withRefresh(
    () => rawRequest(path, opts),
    opts,
  )
  if (response.status >= 400) {
    let detail: unknown = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as Record<
        string,
        unknown
      >
      const fromDetail = normalizeHttpDetail(
        body.detail,
      )
      const fromMessage = normalizeHttpDetail(
        body.message,
      )
      detail =
        fromDetail ||
        fromMessage ||
        `HTTP ${response.status}`
    } catch {
      try {
        detail = await response.text()
      } catch {
        detail = `HTTP ${response.status}`
      }
    }
    throw new AdminApiError(
      response.status,
      detail,
    )
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const adminApi = {
  csrf: () => readCsrfCookie(),
  ensureCsrf: () => ensureCsrf(),
  bootstrapMetadata: () =>
    adminFetch<{
      is_admin: boolean
      admin_init: boolean
      admin_totp_enabled: boolean
      has_backup_codes: boolean
    }>('/auth/metadata', { isUserToken: true }),
  initStart: () =>
    adminFetch<{
      secret_b32: string
      otpauth_uri: string
      ttl_seconds: number
    }>('/auth/init/start', {
      method: 'POST',
      body: {},
      isUserToken: true,
    }),
  initConfirm: (payload: {
    code: string
    fingerprint: string
    label?: string | null
  }) =>
    adminFetch<{
      backup_codes: string[]
      device_id: number
      session: {
        access_token: string
        refresh_token: string
        expires_in: number
        jti: string
        refresh_jti: string
        session_id: number
      }
    }>('/auth/init/confirm', {
      method: 'POST',
      body: payload,
      isUserToken: true,
    }),
  login: (payload: {
    code: string
    fingerprint: string
  }) =>
    adminFetch<{
      requires_device_approval: boolean
      device_id: number | null
      session: {
        access_token: string
        refresh_token: string
        expires_in: number
        jti: string
        refresh_jti: string
        session_id: number
      } | null
    }>('/auth/login', {
      method: 'POST',
      body: payload,
      isUserToken: true,
    }),
  requestDeviceApproval: (
    deviceId: number,
    opts?: { force?: boolean },
  ) =>
    adminFetch<{ detail: string }>(
      '/auth/devices/request-approval',
      {
        method: 'POST',
        body: {
          device_id: deviceId,
          force_resend: opts?.force === true,
        },
        isUserToken: true,
      },
    ),
  confirmDevice: (payload: {
    device_id: number
    email_code: string
    totp_code: string
    label?: string | null
  }) =>
    adminFetch<{
      requires_device_approval: boolean
      device_id: number | null
      session: {
        access_token: string
        refresh_token: string
        expires_in: number
        jti: string
        refresh_jti: string
        session_id: number
      } | null
    }>('/auth/devices/confirm', {
      method: 'POST',
      body: payload,
      isUserToken: true,
    }),
  stepUp: (payload: {
    code: string
    action: string
  }) =>
    adminFetch<{ detail: string }>(
      '/auth/step-up',
      { method: 'POST', body: payload },
    ),
  refresh: async () => {
    const result = await tryRefreshDetailed()
    if (!result) {
      throw new AdminApiError(
        401,
        'refresh failed',
      )
    }
    return result
  },
  logout: () =>
    adminFetch<{ detail: string }>('/auth/logout', {
      method: 'POST',
    }),
  listDevices: () =>
    adminFetch<{
      items: Array<{
        id: number
        label: string | null
        fingerprint_hash_preview: string
        ip_first: string | null
        ua_first: string | null
        trusted_at: string | null
        last_seen_at: string | null
        created_at: string
      }>
    }>('/auth/devices'),
  revokeDevice: (id: number) =>
    adminFetch<{ detail: string }>(
      `/auth/devices/${id}`,
      { method: 'DELETE' },
    ),
  dashboardOverview: () =>
    adminFetch<{
      generated_at: number
      users: {
        total: number
        active: number
        admins: number
        new_24h: number
        online_now: number
      }
      tracks: {
        total: number
        active: number
        new_24h: number
        storage_bytes: number
      }
      complaints: { open: number }
      jobs: { active: number; failed_1h: number }
    }>('/dashboard/overview'),
  dashboardComputeJobs: (
    periodHours: number,
    bucketMinutes: number,
  ) =>
    adminFetch<{
      generated_at: number
      period_hours: number
      bucket_minutes: number
      total: number
      by_status: Record<string, number>
      pending: number
      claimed: number
      succeeded_total: number
      failed_total: number
      resolved_total: number
      succeeded_period: number
      failed_period: number
      resolved_period: number
      buckets: Array<{
        ts: number
        created: number
        succeeded: number
        failed: number
        resolved: number
      }>
    }>('/dashboard/compute-jobs', {
      query: {
        period_hours: periodHours,
        bucket_minutes: bucketMinutes,
      },
    }),
  dashboardTaskiq: (
    periodHours: number,
    bucketMinutes: number,
  ) =>
    adminFetch<{
      generated_at: number
      period_hours: number
      bucket_minutes: number
      total: number
      by_status: Record<string, number>
      queued: number
      running: number
      cancelling: number
      cancelled_total: number
      in_redis_total: number
      queue_lengths: Record<string, number>
      succeeded_total: number
      failed_total: number
      resolved_total: number
      succeeded_period: number
      failed_period: number
      resolved_period: number
      buckets: Array<{
        ts: number
        created: number
        succeeded: number
        failed: number
        resolved: number
      }>
    }>('/dashboard/taskiq', {
      query: {
        period_hours: periodHours,
        bucket_minutes: bucketMinutes,
      },
    }),
  purgePendingComputeJobs: (olderThanHours: number) =>
    adminFetch<{
      deleted: number
      older_than_hours: number
      remaining_pending: number
    }>('/dashboard/compute-jobs/purge-pending', {
      method: 'POST',
      body: { older_than_hours: olderThanHours },
    }),
  dashboardStats: (period: 'today' | '7d' | '30d' | 'all') =>
    adminFetch<{
      period: 'today' | '7d' | '30d' | 'all'
      from_ts: number | null
      to_ts: number
      users_registered: number
      tracks_uploaded: number
      listens_total: number
      unique_listeners: number
      completed_listens: number
      skips: number
      complaints_new: number
      complaints_open: number
      top_tracks: Array<{
        track_id: number
        title: string
        plays: number
        unique_listeners: number
      }>
    }>('/dashboard/stats', {
      query: { period },
    }),
  dashboardTrackStats: (period: 'today' | '7d' | '30d' | 'all') =>
    adminFetch<{
      period: 'today' | '7d' | '30d' | 'all'
      from_ts: number | null
      to_ts: number
      top_tracks: Array<{
        track_id: number
        title: string
        plays: number
        unique_listeners: number
      }>
      uploads_series: Array<{
        ts: number
        value: number
      }>
    }>('/dashboard/track-stats', {
      query: { period },
    }),
  dashboardAdminStats: (period: 'today' | '7d' | '30d' | 'all') =>
    adminFetch<{
      period: 'today' | '7d' | '30d' | 'all'
      from_ts: number | null
      to_ts: number
      total_actions: number
      unique_admins: number
      top_admins: Array<{
        user_id: number
        name: string
        actions: number
      }>
      actions_series: Array<{
        ts: number
        value: number
      }>
    }>('/dashboard/admin-stats', {
      query: { period },
    }),
  dashboardActivationFunnel: (
    period: 'today' | '7d' | '30d' | 'all',
  ) =>
    adminFetch<{
      period: 'today' | '7d' | '30d' | 'all'
      from_ts: number | null
      to_ts: number
      users: {
        auth_success: number
        onboarding_complete: number
        onboarding_skip: number
        home_first_play: number
        home_first_session_start: number
      }
      events: {
        auth_success: number
        onboarding_complete: number
        onboarding_skip: number
        home_first_play: number
        home_first_session_start: number
      }
      avg_auth_to_first_play_seconds: number
      skip_rate: number
      first_session_plays_count: number
    }>('/dashboard/activation-funnel', {
      query: { period },
    }),
  containers: () =>
    adminFetch<{
      counts: {
        ok: number
        warning: number
        error: number
        unknown: number
      }
      total: number
      generated_at: number
      containers: Array<{
        name: string
        status: string
        health: string
        uptime_seconds: number | null
        restart_count: number
        cpu_pct: number | null
        mem_mb: number | null
        image: string | null
      }>
    }>('/dashboard/containers'),
  systemResources: (minutes: number) =>
    adminFetch<{
      generated_at: number
      current: {
        ts: number
        source: string
        cpu_pct: number | null
        load_avg: {
          one: number | null
          five: number | null
          fifteen: number | null
        }
        memory: {
          total_bytes: number | null
          used_bytes: number | null
          available_bytes: number | null
          used_pct: number | null
        }
        storage: {
          path: string
          total_bytes: number | null
          used_bytes: number | null
          free_bytes: number | null
          used_pct: number | null
        }
      }
      history: Array<{
        ts: number
        cpu_pct: number | null
        memory_used_pct: number | null
        storage_used_pct: number | null
      }>
    }>('/dashboard/system-resources', {
      query: { minutes },
    }),
  dashboardRadioAutoSkipReasons: (
    days: number,
    limit: number = 10,
  ) =>
    adminFetch<{
      generated_at: number
      days: number
      items: Array<{
        error_code: string
        error_reason: string
        count: number
      }>
    }>('/dashboard/radio-auto-skip-reasons', {
      query: { days, limit },
    }),
  servicesHealth: () =>
    adminFetch<Record<string, unknown>>(
      '/system/services',
    ),
  outboundStatus: () =>
    adminFetch<{
      available: boolean
      error?: string
      mode?: 'direct' | 'proxy' | 'tor' | 'hybrid'
      tor?: {
        available: boolean
        circuit_uses_cap: number
        newnym_min_interval_s: number
        control_port: number | null
      }
      proxies?: {
        configured: number
        prefer_tor: boolean
      }
      quarantine?: {
        active_total: number
        active_tor_circuits: number
        active_proxies: number
        default_ttl_s: number
      }
      limits?: {
        default_timeout_s: number
        max_retries: number
        backoff_base_s: number
        backoff_cap_s: number
        breaker_failure_threshold: number
        breaker_reset_s: number
      }
      backend?: string
      services?: Array<{
        service: string
        requests: number
        transport_errors: number
        breaker: string
        by_status: Record<string, number>
      }>
      recent_requests?: Array<{
        ts: number
        service: string
        method: string
        host: string
        path: string
        transport: string
        identity: string | null
        egress_ip?: string | null
        status_code: number | null
        duration_ms: number | null
        error: string | null
      }>
      rotation_events?: Record<string, number>
      burned_identities?: Record<string, number>
    }>('/system/outbound-status'),
  dashboardTimeseries: (
    metric: string,
    minutes: number,
    stepSeconds: number,
  ) =>
    adminFetch<Record<string, unknown>>(
      '/dashboard/timeseries',
      {
        query: {
          metric,
          minutes,
          step_seconds: stepSeconds,
        },
      },
    ),
  metricsAllowlist: () =>
    adminFetch<{ metrics: string[] }>(
      '/dashboard/metrics-allowlist',
    ),
  auditLoginHistory: (
    userId?: number,
    limit: number = 100,
  ) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      user_id: number | null
      count: number
    }>('/audit/login-history', {
      query: { user_id: userId, limit },
    }),
  listBackups: () =>
    adminFetch<{
      root: string
      remote_configured: boolean
      daily: Array<Record<string, unknown>>
      weekly: Array<Record<string, unknown>>
      monthly: Array<Record<string, unknown>>
      scanned_at: string
    }>('/system/backups'),
  runBackup: (kind: string) =>
    adminFetch<{
      queued: boolean
      task_id: string | null
      kind: string
    }>('/system/backups/run', {
      method: 'POST',
      body: { kind },
    }),
  antiAbuseEvents: (limit: number = 100) =>
    adminFetch<{
      items: Array<{
        id: string
        data: Record<string, string>
      }>
      count: number
    }>('/security/anti-abuse-events', {
      query: { limit },
    }),
  featureFlags: () =>
    adminFetch<{
      items: Array<{
        key: string
        value: Record<string, unknown>
        updated_by: number | null
        updated_at: string
      }>
    }>('/system/feature-flags'),
  setFeatureFlag: (name: string, enabled: boolean) =>
    adminFetch<{
      key: string
      value: Record<string, unknown>
    }>(`/system/feature-flags/${name}`, {
      method: 'PATCH',
      body: { enabled },
    }),
  knownCapabilities: () =>
    adminFetch<{ capabilities: string[] }>(
      '/system/known-capabilities',
    ),
  logsLabels: () =>
    adminFetch<{
      labels: string[]
      levels: string[]
    }>('/logs/labels'),
  logsQuery: (params: {
    container?: string
    service?: string
    level?: string
    contains?: string
    minutes?: number
    limit?: number
  }) =>
    adminFetch<{
      items: Array<{
        ts_ns: number
        labels: Record<string, string>
        line: string
      }>
      selectors: Record<string, string>
      minutes: number
      count: number
    }>('/logs/query', { query: params }),
  metricsList: () =>
    adminFetch<{ metrics: string[] }>(
      '/metrics/list',
    ),
  metricRange: (
    name: string,
    minutes: number,
    stepSeconds: number,
  ) =>
    adminFetch<Record<string, unknown>>(
      '/metrics/range',
      {
        query: {
          name,
          minutes,
          step_seconds: stepSeconds,
        },
      },
    ),
  metricInstant: (name: string) =>
    adminFetch<Record<string, unknown>>(
      '/metrics/instant',
      { query: { name } },
    ),
  listUsers: (params: {
    page?: number
    size?: number
    is_active?: boolean
    is_admin?: boolean
    search?: string
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/users', { query: params }),
  listArtists: (params: {
    page?: number
    size?: number
    q?: string
    enrichment?: string
    catalog_sync?: string
  }) =>
    adminFetch<{
      items: Array<{
        id: number
        name: string
        image_key: string | null
        image_url: string | null
        source: string
        bio: string | null
        birth_date: string | null
        birthplace: string | null
        country: string | null
        website_url: string | null
        enrichment_status: string
        enrichment_confidence: number | null
        enriched_at: string | null
        created_at: string
        updated_at: string | null
        monthly_listeners: number
        catalog_sync_state: 'idle' | 'running' | 'success' | 'error'
        catalog_sync_mode: string | null
        catalog_sync_updated_at: string | null
      }>
      total: number
    }>('/artists', { query: params }),
  listArtistIds: (params: {
    q?: string
    enrichment?: string
    catalog_sync?: string
  }) =>
    adminFetch<{
      ids: number[]
      total: number
    }>('/artists/ids', { query: params }),
  getArtistPipelineHealth: () =>
    adminFetch<{
      enrichment_counts: Record<string, number>
      total: number
    }>('/artists/pipeline-health'),
  artistEnrichBatch: (artistIds: number[]) =>
    adminFetch<{
      queued: number
      job_ids: Record<string, string | null>
      errors: Array<{ artist_id: number; detail: string }>
    }>('/artists/enrich-batch', {
      method: 'POST',
      body: { artist_ids: artistIds, bypass_cache: true },
    }),
  getQueueDepth: () =>
    adminFetch<{ queue_length: number | null; available: boolean }>(
      '/system/queue-depth',
    ),

  getStationGapArtists: (params: {
    min_tracks?: number
    page?: number
    size?: number
    include_sync_disabled?: boolean
  }) =>
    adminFetch<{
      items: Array<{
        id: number
        name: string
        image_key: string | null
        soundcloud_user_id: number | null
        catalog_sync_enabled: boolean
        station_track_count: number | null
        station_synced_at: string | null
      }>
      total: number
      min_tracks: number
    }>('/artists/station-gap', { query: params }),
  bulkResyncStations: (
    artistIds: number[],
    skipBackgroundLyrics = false,
  ) =>
    adminFetch<{
      queued: number
      job_ids: Record<string, string | null>
      errors: Array<{ artist_id: number; detail: string }>
    }>('/artists/station-gap/resync-bulk', {
      method: 'POST',
      body: {
        artist_ids: artistIds,
        skip_background_lyrics: skipBackgroundLyrics,
      },
    }),
  listDeletedUsers: (params: {
    page?: number
    size?: number
    search?: string
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/users/deleted', {
      method: 'GET',
      query: {
        page: params.page ?? 1,
        size: params.size ?? 25,
        ...(params.search ? { search: params.search } : {}),
      },
    }),
  restoreUser: (userId: number) =>
    adminFetch<Record<string, unknown>>(
      `/users/${userId}/restore`,
      { method: 'POST', body: {} },
    ),
  hardDeleteUserForever: (userId: number) =>
    adminFetch<void>(`/users/${userId}/forever`, {
      method: 'DELETE',
    }),
  banUser: (userId: number) =>
    adminFetch<{ id: number; is_active: boolean }>(
      `/users-ext/${userId}/ban`,
      { method: 'POST', body: {} },
    ),
  unbanUser: (userId: number) =>
    adminFetch<{ id: number; is_active: boolean }>(
      `/users-ext/${userId}/unban`,
      { method: 'POST', body: {} },
    ),
  forceLogoutUser: (userId: number) =>
    adminFetch<{
      user_id: number
      admin_sessions_revoked: number
    }>(`/users-ext/${userId}/force-logout`, {
      method: 'POST',
      body: {},
    }),
  sendAdminMessage: (userId: number, text: string) =>
    adminFetch<{
      conversation_id: number
      message_id: number | null
    }>(`/users-ext/${userId}/message`, {
      method: 'POST',
      body: { text },
    }),
  getTrackVisibilityCounts: (params?: { search?: string }) =>
    adminFetch<{ hidden: number; visible: number }>(
      '/tracks/visibility-counts',
      { query: params },
    ),
  listTracks: (params: {
    page?: number
    size?: number
    is_active?: boolean
    without_lyrics?: boolean
    lyrics_catalog_miss_only?: boolean
    lyrics_sync_status?: 'synced' | 'unsynced' | 'missing'
    search?: string
    for_playlist_owner_id?: number
    playable_only?: boolean
    sort_by?: 'created_at_desc' | 'visibility_asc' | 'visibility_desc'
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tracks', { query: params }),
  listTrackIds: (params: {
    scope?:
      | 'all'
      | 'playback_failures'
      | 'playback_suppressed'
      | 'sc_encrypted_unsupported'
      | 'deleted'
    is_active?: boolean
    without_lyrics?: boolean
    lyrics_catalog_miss_only?: boolean
    lyrics_sync_status?: 'synced' | 'unsynced' | 'missing'
    search?: string
    playback_error?: string
    for_playlist_owner_id?: number
    playable_only?: boolean
  }) =>
    adminFetch<{
      ids: number[]
      total: number
    }>('/tracks/ids', { query: params }),
  listTracksPlaybackUnavailable: (params: {
    page?: number
    size?: number
    search?: string
    playback_error?: string
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tracks/playback-health/unavailable', { query: params }),
  listTracksPlaybackSuppressed: (params: {
    page?: number
    size?: number
    search?: string
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tracks/playback-health/suppressed', { query: params }),
  listTracksSoundCloudEncryptedUnsupported: (params: {
    page?: number
    size?: number
    search?: string
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tracks/playback-health/soundcloud-encrypted-unsupported', {
      query: params,
    }),
  cleanupSoundCloudEncryptedUnsupported: (params?: {
    limit?: number
    dry_run?: boolean
  }) =>
    adminFetch<{
      matched: number
      updated: number
      dry_run: boolean
      track_ids: number[]
      detail: string
    }>('/tracks/playback-health/cleanup-soundcloud-encrypted-unsupported', {
      method: 'POST',
      body: {
        limit: params?.limit,
        dry_run: params?.dry_run,
      },
    }),
  clearTrackPlaybackSuppression: (trackId: number) =>
    adminFetch<Record<string, unknown>>(
      `/tracks/${trackId}/playback-health/clear-suppression`,
      { method: 'POST', body: {} },
    ),
  verifyTrackPlayback: (trackId: number) =>
    adminFetch<{
      ok: boolean
      detail: string
      http_status: number | null
      effective_track_id: number | null
      stream_protocol: string | null
    }>(`/tracks/${trackId}/playback-health/verify`, {
      method: 'POST',
      body: {},
    }),
  repairTrackPlayback: (trackId: number) =>
    adminFetch<{
      queued: boolean
      track_id: number
      job_id: string | null
      progress_id: string | null
      detail: string
    }>(`/tracks/${trackId}/playback-health/repair`, {
      method: 'POST',
      body: {},
    }),
  repairTracksPlayback: (trackIds: number[]) =>
    adminFetch<{
      requested: number
      queued: number
      skipped: number
      missing: number
      job_ids: string[]
      progress_ids: string[]
      detail: string
    }>('/tracks/playback-health/repair', {
      method: 'POST',
      body: { track_ids: trackIds },
    }),
  normalizeTelegramPlayback: (params?: {
    limit?: number
    dry_run?: boolean
  }) =>
    adminFetch<{
      dry_run: boolean
      found: number
      enqueued: number
      failed: number
      items: Array<{
        track_id: number
        status: string
        title: string
        file_key: string
        tmp_key: string | null
        error: string | null
      }>
      detail: string
    }>('/tracks/playback-health/normalize-telegram', {
      method: 'POST',
      body: {
        limit: params?.limit,
        dry_run: params?.dry_run,
      },
    }),
  auditSoundCloudPlayback: (params?: {
    search?: string
    limit?: number
    include_recently_checked?: boolean
  }) =>
    adminFetch<{
      requested: number
      queued: number
      skipped: number
      missing: number
      job_ids: string[]
      progress_ids: string[]
      detail: string
    }>('/tracks/playback-health/audit-soundcloud', {
      method: 'POST',
      body: {
        search: params?.search,
        limit: params?.limit,
        include_recently_checked: params?.include_recently_checked,
      },
    }),
  clearTrackPlaybackDiagnostics: (trackId: number) =>
    adminFetch<Record<string, unknown>>(
      `/tracks/${trackId}/playback-health/clear-diagnostics`,
      { method: 'POST', body: {} },
    ),
  fullRestoreTrackPlayback: (trackId: number) =>
    adminFetch<Record<string, unknown>>(
      `/tracks/${trackId}/playback-health/full-restore`,
      { method: 'POST', body: {} },
    ),
  diagnoseSoundCloudTrack: (url: string) =>
    adminFetch<SoundCloudDiagnoseResponse>(
      '/soundcloud/diagnose',
      {
        query: { url },
      },
    ),
  listAdminAlbums: (params: {
    page?: number
    size?: number
    search?: string
  }) =>
    adminFetch<{
      items: Array<{
        id: number
        title: string
        owner_id: number
        is_public: boolean
        created_at: string
        track_count: number
      }>
      total: number
      page: number
      size: number
    }>('/albums', { query: params }),
  getAdminAlbum: (albumId: number) =>
    adminFetch<{
      id: number
      title: string
      description: string | null
      cover_key: string | null
      owner_id: number
      is_public: boolean
      created_at: string
      tracks: Array<{
        id: number
        title: string
        artist: string | null
      }>
    }>(`/albums/${albumId}`),
  patchAdminAlbum: (
    albumId: number,
    body: {
      title?: string
      description?: string | null
      is_public?: boolean
      owner_id?: number
    },
  ) =>
    adminFetch<Record<string, unknown>>(
      `/albums/${albumId}`,
      { method: 'PATCH', body },
    ),
  uploadAdminAlbumCover: (albumId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return adminFetch<Record<string, unknown>>(
      `/albums/${albumId}/cover`,
      { method: 'POST', body: fd },
    )
  },
  addAdminAlbumTrack: (albumId: number, trackId: number) =>
    adminFetch<void>(
      `/albums/${albumId}/tracks/${trackId}`,
      { method: 'POST' },
    ),
  removeAdminAlbumTrack: (albumId: number, trackId: number) =>
    adminFetch<void>(
      `/albums/${albumId}/tracks/${trackId}`,
      { method: 'DELETE' },
    ),
  reorderAdminAlbumTracks: (
    albumId: number,
    trackIds: number[],
  ) =>
    adminFetch<void>(
      `/albums/${albumId}/track-order`,
      {
        method: 'PUT',
        body: { track_ids: trackIds },
      },
    ),
  listAdminPlaylists: (params: {
    page?: number
    size?: number
    search?: string
  }) =>
    adminFetch<{
      items: Array<{
        id: number
        name: string
        owner_id: number
        is_public: boolean
        playlist_type: string
        is_featured: boolean
        description: string | null
        cover_key: string | null
        source_url: string | null
        created_at: string
        track_count: number
      }>
      total: number
      page: number
      size: number
    }>('/playlists', { query: params }),
  getAdminPlaylist: (playlistId: number) =>
    adminFetch<{
      id: number
      name: string
      owner_id: number
      is_public: boolean
      playlist_type: string
      is_featured: boolean
      description: string | null
      cover_key: string | null
      source_url: string | null
      created_at: string
      tracks: Array<{
        id: number
        title: string
        artist: string | null
      }>
    }>(`/playlists/${playlistId}`),
  patchAdminPlaylist: (
    playlistId: number,
    body: {
      name?: string
      is_public?: boolean
      owner_id?: number
      is_featured?: boolean
      description?: string
    },
  ) =>
    adminFetch<Record<string, unknown>>(
      `/playlists/${playlistId}`,
      { method: 'PATCH', body },
    ),
  importAdminPlaylist: (body: {
    source_url: string
    name?: string
    make_featured?: boolean
    make_public?: boolean
  }) =>
    adminFetch<Record<string, unknown>>(
      '/playlists/import',
      { method: 'POST', body },
    ),
  createEditorialPlaylist: (body: {
    name: string
    description?: string
    is_featured?: boolean
    is_public?: boolean
  }) =>
    adminFetch<Record<string, unknown>>(
      '/playlists/editorial',
      { method: 'POST', body },
    ),
  addAdminPlaylistTrack: (playlistId: number, trackId: number) =>
    adminFetch<void>(
      `/playlists/${playlistId}/tracks/${trackId}`,
      { method: 'POST' },
    ),
  removeAdminPlaylistTrack: (playlistId: number, trackId: number) =>
    adminFetch<void>(
      `/playlists/${playlistId}/tracks/${trackId}`,
      { method: 'DELETE' },
    ),
  listAdminPromotions: (params: {
    page?: number
    size?: number
    entity_type?: string
    is_active?: boolean
    surface?: string
  }) =>
    adminFetch<{
      items: Array<{
        id: number
        entity_type: 'artist' | 'track' | 'playlist' | 'album'
        entity_id: number
        entity_label: string | null
        surfaces: Array<'hero' | 'section' | 'in_feed' | 'search_pin'>
        priority: number
        starts_at: string | null
        ends_at: string | null
        is_active: boolean
        availability: 'available' | 'hidden' | 'missing'
        impressions_total: number
        clicks_total: number
        created_at: string
        updated_at: string
      }>
      total: number
      page: number
      size: number
    }>('/promotions', { query: params }),
  getAdminPromotion: (promotionId: number) =>
    adminFetch<{
      id: number
      entity_type: 'artist' | 'track' | 'playlist' | 'album'
      entity_id: number
      entity_label: string | null
      surfaces: Array<'hero' | 'section' | 'in_feed' | 'search_pin'>
      priority: number
      starts_at: string | null
      ends_at: string | null
      is_active: boolean
      availability: 'available' | 'hidden' | 'missing'
      impressions_total: number
      clicks_total: number
      title_override: string | null
      subtitle_override: string | null
      cta_label_override: string | null
      cover_url_override: string | null
      created_at: string
      updated_at: string
    }>(`/promotions/${promotionId}`),
  createAdminPromotion: (body: {
    entity_type: 'artist' | 'track' | 'playlist' | 'album'
    entity_id: number
    surfaces: Array<'hero' | 'section' | 'in_feed' | 'search_pin'>
    priority?: number
    starts_at?: string | null
    ends_at?: string | null
    is_active?: boolean
    title_override?: string | null
    subtitle_override?: string | null
    cta_label_override?: string | null
    cover_url_override?: string | null
  }) =>
    adminFetch<{ id: number }>('/promotions', {
      method: 'POST',
      body,
    }),
  patchAdminPromotion: (
    promotionId: number,
    body: Record<string, unknown>,
  ) =>
    adminFetch<Record<string, unknown>>(`/promotions/${promotionId}`, {
      method: 'PATCH',
      body,
    }),
  deleteAdminPromotion: (promotionId: number) =>
    adminFetch<void>(`/promotions/${promotionId}`, {
      method: 'DELETE',
    }),
  getAdminPromotionStats: (
    promotionId: number,
    periodDays: number = 30,
  ) =>
    adminFetch<{
      promotion_id: number
      period_days: number
      impressions: number
      clicks: number
      plays: number
      ctr: number
    }>(`/promotions/${promotionId}/stats`, {
      query: { period_days: periodDays },
    }),
  reorderAdminPlaylistTracks: (
    playlistId: number,
    trackIds: number[],
  ) =>
    adminFetch<void>(
      `/playlists/${playlistId}/track-order`,
      {
        method: 'PUT',
        body: { track_ids: trackIds },
      },
    ),
  deleteTrack: (trackId: number, reason: string = 'admin') =>
    adminFetch<void>(`/tracks/${trackId}`, {
      method: 'DELETE',
      query: { reason },
    }),
  restoreTrack: (trackId: number) =>
    adminFetch<Record<string, unknown>>(
      `/tracks/${trackId}/restore`,
      { method: 'POST' },
    ),
  hardDeleteTrackForever: (trackId: number) =>
    adminFetch<void>(`/tracks/${trackId}/forever`, {
      method: 'DELETE',
    }),
  listDeletedTracks: (params: {
    page?: number
    size?: number
    search?: string
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>(`/tracks/deleted`, {
      method: 'GET',
      query: {
        page: params.page ?? 1,
        size: params.size ?? 25,
        ...(params.search ? { search: params.search } : {}),
      },
    }),
  setTrackVisibility: (
    trackId: number,
    isActive: boolean,
  ) =>
    adminFetch<Record<string, unknown>>(
      `/tracks/${trackId}/visibility`,
      {
        method: 'PATCH',
        query: { is_active: isActive },
      },
    ),
  updateTrackGenre: (
    trackId: number,
    genre: string | null,
  ) =>
    adminFetch<Record<string, unknown>>(
      `/tracks/${trackId}/genre`,
      {
        method: 'PATCH',
        body: { genre },
      },
    ),
  listComplaints: (params: {
    page?: number
    size?: number
    unresolved_only?: boolean
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/complaints', { query: params }),
  listLyricsJobs: (params: {
    status?: string
    profile?: string
    page?: number
    size?: number
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tasks/lyrics-jobs', { query: params }),
  listComputeJobs: (params: {
    status?: string
    job_type?: string
    page?: number
    size?: number
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tasks/compute-jobs', { query: params }),
  getLyricsJob: (jobId: string) =>
    adminFetch<{
      id: string
      track_id: number
      status: string
      profile: string
      routed_to_worker: string | null
      attempts: number
      error: string | null
      started_at: string | null
      finished_at: string | null
      duration_ms: number | null
      created_at: string
      progress_id: string | null
      requested_by_user_id: number | null
      current_tier?: string | null
      tiers_planned?: string[] | null
      request_with_sync?: boolean
      request_bypass_cache?: boolean
      request_align_existing_text?: boolean
      live: {
        stage: string | null
        percent: number | null
        terminal_state: string | null
        logs: string[]
      } | null
    }>(`/tasks/lyrics-jobs/${jobId}`),
  cancelLyricsJob: (jobId: string) =>
    adminFetch<{
      status: string
      job_status?: string
    }>(`/tasks/lyrics-jobs/${jobId}/cancel`, {
      method: 'POST',
      body: {},
    }),
  // Same body as /tasks/lyrics-jobs/.../cancel; path uses audio_compute.manage.
  cancelComputeJob: (jobId: string) =>
    adminFetch<{
      status: string
      job_status?: string
    }>(`/audio-compute/jobs/${jobId}/cancel`, {
      method: 'POST',
      body: {},
    }),
  reapExpiredLyricsLeases: () =>
    adminFetch<{
      status: string
      expired_leases_handled: number
    }>(
      '/audio-compute/operations/reap-expired-leases',
      {
        method: 'POST',
        body: {},
      },
    ),
  cancelComputeJobByProgress: (progressId: string) =>
    adminFetch<{
      status: string
      job_status?: string
      job_id: string
    }>('/audio-compute/jobs/cancel-by-progress', {
      method: 'POST',
      body: { progress_id: progressId },
    }),
  patchLyricsJobRouting: (
    jobId: string,
    body: {
      pinned_worker_id: string | null
      queue_priority: number
    },
  ) =>
    adminFetch<Record<string, unknown>>(
      `/audio-compute/jobs/${encodeURIComponent(jobId)}/routing`,
      { method: 'PATCH', body },
    ),
  listGenericComputeJobs: (params?: {
    status?: string
    job_type?: string
    limit?: number
  }) =>
    adminFetch<
      Array<{
        id: string
        job_type: string
        target_kind: string | null
        target_id: string | null
        feature_version: string | null
        status: string
        priority: number
        attempts: number
        max_attempts: number | null
        pinned_worker_id: string | null
        claimed_by: string | null
        last_error: string | null
        created_at: string | null
        finished_at: string | null
        next_attempt_at: string | null
      }>
    >('/audio-compute/generic-compute-jobs', {
      query: params,
    }),
  patchGenericComputeJobRouting: (
    jobId: string,
    body: {
      pinned_worker_id: string | null
      priority: number
      release_claim: boolean
    },
  ) =>
    adminFetch<Record<string, unknown>>(
      `/audio-compute/generic-compute-jobs/${encodeURIComponent(jobId)}/routing`,
      { method: 'PATCH', body },
    ),
  cancelAllQueuedLyricsJobs: () =>
    adminFetch<{
      cancelled: number
      items: string[]
    }>(`/tasks/lyrics-jobs/cancel-queued`, {
      method: 'POST',
      body: {},
    }),
  listQueues: () =>
    adminFetch<{
      items: Array<{
        name: string
        length: number | null
      }>
    }>('/tasks/queues'),
  listSchedules: () =>
    adminFetch<{
      items: Array<{
        id: string
        name: string
        task_name: string
        queue: string
        cron: string
        payload: Record<string, unknown> | null
        enabled: boolean
        last_run_at: string | null
        next_run_at: string | null
        last_status: string | null
        last_error: string | null
        last_job_id: string | null
        created_at: string
        updated_at: string
      }>
    }>('/tasks/schedules'),
  createSchedule: (body: {
    name: string
    task_name: string
    cron: string
    queue?: string
    payload?: Record<string, unknown> | null
    enabled?: boolean
  }) =>
    adminFetch<Record<string, unknown>>(
      '/tasks/schedules',
      { method: 'POST', body },
    ),
  updateSchedule: (
    id: string,
    body: {
      cron?: string
      task_name?: string
      queue?: string
      payload?: Record<string, unknown> | null
      enabled?: boolean
    },
  ) =>
    adminFetch<Record<string, unknown>>(
      `/tasks/schedules/${id}`,
      { method: 'PATCH', body },
    ),
  deleteSchedule: (id: string) =>
    adminFetch<{ deleted: string }>(
      `/tasks/schedules/${id}`,
      { method: 'DELETE' },
    ),
  runScheduleNow: (id: string) =>
    adminFetch<{ job_id: string; schedule_id: string }>(
      `/tasks/schedules/${id}/run-now`,
      { method: 'POST', body: {} },
    ),
  listBackgroundJobs: (params: {
    name?: string
    queue?: string
    status?: string
    scheduled_job_id?: string
    page?: number
    size?: number
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tasks/jobs', { query: params }),
  playbackRepairSummary: (jobIds: string[]) =>
    adminFetch<PlaybackRepairSummary>(
      '/tasks/playback-repair/summary',
      {
        method: 'POST',
        body: { job_ids: jobIds },
      },
    ),
  retryUnresolvedPlaybackRepairs: (jobIds: string[]) =>
    adminFetch<{
      requested: number
      queued: number
      skipped: number
      missing: number
      job_ids: string[]
      progress_ids: string[]
      detail: string
    }>('/tasks/playback-repair/retry-unresolved', {
      method: 'POST',
      body: { job_ids: jobIds },
    }),
  listActiveBackgroundJobs: () =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
    }>('/tasks/jobs/active'),
  getBackgroundJob: (id: string) =>
    adminFetch<Record<string, unknown>>(`/tasks/jobs/${id}`),
  cancelBackgroundJob: (id: string) =>
    adminFetch<Record<string, unknown>>(
      `/tasks/jobs/${id}/cancel`,
      { method: 'POST', body: {} },
    ),
  cancelActiveBackgroundJobs: (body: {
    name?: string
    queue?: string
    status?: string
    scheduled_job_id?: string
  }) =>
    adminFetch<{
      matched: number
      cancelled: number
      cancelling: number
      purged_messages: number
      items: string[]
    }>('/tasks/jobs/cancel-active', {
      method: 'POST',
      body,
    }),
  retryBackgroundJob: (id: string) =>
    adminFetch<{ new_job_id: string; parent_job_id: string }>(
      `/tasks/jobs/${id}/retry`,
      { method: 'POST', body: {} },
    ),
  tasksOverview: () =>
    adminFetch<{
      queues: Array<{ name: string; length: number | null }>
      background_jobs: Record<string, number>
      compute_jobs: Record<string, number>
      lyrics_jobs: Record<string, number>
      upcoming_schedules: Array<Record<string, unknown>>
    }>('/tasks/overview'),
  tasksListTypes: (periodHours = 24) =>
    adminFetch<{
      period_hours: number
      paused: Record<
        string,
        {
          paused_at: string | null
          by_admin_id: number | null
          reason: string | null
        }
      >
      items: Array<{
        name: string
        kind: 'taskiq' | 'compute' | 'mixed'
        paused: boolean
        paused_meta: {
          paused_at: string | null
          by_admin_id: number | null
          reason: string | null
        } | null
        by_status: Record<string, number>
        done_period: number
        failed_period: number
        avg_duration_ms: number | null
        max_duration_ms: number | null
        schedules: Array<{
          id: string
          name: string
          cron: string
          enabled: boolean
          next_run_at: string | null
        }>
      }>
    }>('/tasks/types', { query: { period_hours: periodHours } }),
  tasksPauseType: (name: string, opts?: { reason?: string; drain?: boolean }) =>
    adminFetch<{
      task_name: string
      paused: boolean
      meta: Record<string, unknown>
      drained: { background_jobs: number; compute_jobs: number } | null
    }>(`/tasks/types/${encodeURIComponent(name)}/pause`, {
      method: 'POST',
      body: {
        reason: opts?.reason ?? null,
        drain: !!opts?.drain,
      },
    }),
  tasksAffectedPreview: (name: string) =>
    adminFetch<{ background_jobs: number; compute_jobs: number }>(
      `/tasks/types/${encodeURIComponent(name)}/affected`,
    ),
  tasksTypeTimeseries: (
    name: string,
    periodHours = 6,
    bucketMinutes = 5,
  ) =>
    adminFetch<{
      task_name: string
      period_hours: number
      bucket_seconds: number
      buckets: Array<{
        ts: number
        created: number
        succeeded: number
        failed: number
      }>
      p95_duration_ms: number | null
      avg_duration_ms: number | null
      max_duration_ms: number | null
      samples: number
    }>(`/tasks/types/${encodeURIComponent(name)}/timeseries`, {
      query: {
        period_hours: periodHours,
        bucket_minutes: bucketMinutes,
      },
    }),
  tasksManualEnqueue: (params: {
    task_name: string
    payload?: Record<string, unknown>
    queue?: string
    max_attempts?: number
  }) =>
    adminFetch<{
      job_id: string
      task_name: string
      queue: string
    }>('/tasks/manual', {
      method: 'POST',
      body: {
        task_name: params.task_name,
        payload: params.payload ?? {},
        queue: params.queue ?? 'default',
        max_attempts: params.max_attempts ?? 3,
      },
    }),
  tasksResumeType: (name: string) =>
    adminFetch<{
      task_name: string
      paused: boolean
      removed: boolean
    }>(`/tasks/types/${encodeURIComponent(name)}/resume`, {
      method: 'POST',
      body: {},
    }),
  tasksListWorkers: () =>
    adminFetch<{
      workers: Array<{
        id: string
        name: string
        profile: string
        active: boolean
        max_concurrent_jobs: number
        last_seen_at: string | null
        last_ip: string | null
        revoked_at: string | null
        suspended_until: string | null
        suspended_reason: string | null
        claims_paused_until: string | null
        claims_pause_reason: string | null
        worker_package_version: string | null
        current_claims: number
        recent_throughput_5m: number
        anomaly_flags_in_window: number
      }>
      scheduler_leader: {
        owner: string | null
        ttl_seconds: number | null
      }
    }>('/tasks/workers'),
  tasksListAudit: (params: {
    page?: number
    size?: number
    action_prefix?: string
    user_id?: number
  }) =>
    adminFetch<{
      items: Array<{
        id: number
        user_id: number
        action: string
        target_type: string | null
        target_id: string | null
        ip: string | null
        meta: Record<string, unknown> | null
        created_at: string
      }>
      total: number
      page: number
      size: number
    }>('/tasks/audit', { query: params }),
  tasksPurgeBackgroundJobs: (params: {
    older_than_hours: number
    statuses?: string[]
    name?: string
  }) =>
    adminFetch<{
      deleted: number
      older_than_hours: number
      statuses: string[]
    }>('/tasks/jobs/purge', {
      method: 'POST',
      body: params,
    }),
  tasksPurgeComputeJobs: (params: {
    older_than_hours: number
    status?: string
  }) =>
    adminFetch<{
      deleted: number
      older_than_hours: number
      status: string
      remaining: number
    }>('/tasks/compute-jobs/purge', {
      method: 'POST',
      body: params,
    }),
  tasksListAllowed: () =>
    adminFetch<{ tasks: string[] }>('/tasks/allowed'),
  tasksRunAllowed: (taskName: string, payload?: Record<string, unknown>) =>
    adminFetch<{
      task_id: string | null
      task_name: string
      queued: boolean
    }>(`/tasks/run/${encodeURIComponent(taskName)}`, {
      method: 'POST',
      body: payload ?? {},
    }),
  listAudit: (params: {
    user_id?: number
    action?: string
    target_type?: string
    page?: number
    size?: number
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/audit/', { query: params }),
  loginAttempts: (params: {
    failed_only?: boolean
    minutes?: number
    limit?: number
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
    }>('/security/login-attempts', { query: params }),
  lockedUsers: () =>
    adminFetch<{
      items: Array<{
        user_id: number
        ttl_seconds: number | null
      }>
    }>('/security/locked-users'),
  releaseLockout: (userId: number) =>
    adminFetch<{
      user_id: number
      released: boolean
    }>(`/security/lockout/${userId}/release`, {
      method: 'POST',
      body: {},
    }),

  getAiSettings: () =>
    adminFetch<{
      track_info_ttl_days: number
      artist_supplemental_ttl_days: number
    }>('/system/ai-settings'),

  updateAiSettings: (data: {
    track_info_ttl_days?: number
    artist_supplemental_ttl_days?: number
  }) =>
    adminFetch<{
      track_info_ttl_days: number
      artist_supplemental_ttl_days: number
    }>('/system/ai-settings', {
      method: 'PUT',
      body: data,
    }),
  getRadioTuning: () =>
    adminFetch<{
      enabled: boolean
      ab_split_percent_b: number
      variant_a: Record<string, number>
      variant_b: Record<string, number>
    }>('/system/radio-tuning'),
  updateRadioTuning: (data: {
    enabled?: boolean
    ab_split_percent_b?: number
    variant_a?: Record<string, number>
    variant_b?: Record<string, number>
  }) =>
    adminFetch<{
      enabled: boolean
      ab_split_percent_b: number
      variant_a: Record<string, number>
      variant_b: Record<string, number>
    }>('/system/radio-tuning', {
      method: 'PUT',
      body: data,
    }),

  catalogOverview: (artistId: number) =>
    adminFetch<{
      artist_id: number
      image_key: string | null
      soundcloud_user_id: number | null
      soundcloud_permalink: string | null
      catalog_sync_enabled: boolean
      releases: Array<{
        id: number
        title: string
        release_kind: string | null
        released_at: string | null
        display_position: number
        track_count: number
        cover_key: string | null
        manual_lock: boolean
        soundcloud_album_id: number | null
      }>
      releases_total: number
      catalog_sync_state:
        | 'idle'
        | 'running'
        | 'success'
        | 'error'
      catalog_sync_mode: 'full' | 'release' | 'station' | null
      catalog_sync_soundcloud_album_id: number | null
      catalog_sync_error: string | null
      catalog_sync_detail: Record<string, unknown> | null
      catalog_sync_updated_at: string | null
    }>(`/artists/${artistId}/catalog/overview`),

  catalogStationProbe: (artistId: number) =>
    adminFetch<{
      artist_id: number
      artist_name: string
      soundcloud_user_id: number | null
      station_status:
        | 'ok'
        | 'missing_soundcloud_user'
        | 'not_available'
        | 'error'
      reason: string | null
      station_soundcloud_album_id: number | null
      station_title: string | null
      fetched_track_count: number
      importable_track_count: number
      existing_release_id: number | null
      existing_release_track_count: number | null
      tracks: Array<{
        ref: string | null
        title: string | null
        artist: string | null
        permalink_url: string | null
        importable: boolean
        reject_reason: string | null
      }>
    }>(`/artists/${artistId}/catalog/station-probe`),

  catalogUploadAvatar: (artistId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return adminFetch<{
      artist_id: number
      image_key: string | null
      soundcloud_user_id: number | null
      soundcloud_permalink: string | null
      releases: Array<{
        id: number
        title: string
        release_kind: string | null
        released_at: string | null
        display_position: number
        track_count: number
        cover_key: string | null
        manual_lock: boolean
        soundcloud_album_id: number | null
      }>
      releases_total: number
      catalog_sync_state:
        | 'idle'
        | 'running'
        | 'success'
        | 'error'
      catalog_sync_mode: 'full' | 'release' | 'station' | null
      catalog_sync_soundcloud_album_id: number | null
      catalog_sync_error: string | null
      catalog_sync_detail: Record<string, unknown> | null
      catalog_sync_updated_at: string | null
    }>(`/artists/${artistId}/catalog/avatar`, {
      method: 'POST',
      body: fd,
    })
  },

  catalogPatchSoundcloud: (
    artistId: number,
    body: {
      soundcloud_user_id?: number | null
      soundcloud_permalink?: string | null
    },
  ) =>
    adminFetch<{
      artist_id: number
      image_key: string | null
      soundcloud_user_id: number | null
      soundcloud_permalink: string | null
      releases: Array<{
        id: number
        title: string
        release_kind: string | null
        released_at: string | null
        display_position: number
        track_count: number
        cover_key: string | null
        manual_lock: boolean
        soundcloud_album_id: number | null
      }>
      releases_total: number
      catalog_sync_state:
        | 'idle'
        | 'running'
        | 'success'
        | 'error'
      catalog_sync_mode: 'full' | 'release' | 'station' | null
      catalog_sync_soundcloud_album_id: number | null
      catalog_sync_error: string | null
      catalog_sync_detail: Record<string, unknown> | null
      catalog_sync_updated_at: string | null
    }>(`/artists/${artistId}/catalog/soundcloud`, {
      method: 'PATCH',
      body,
    }),

  catalogReleaseDetail: (artistId: number, releaseId: number) =>
    adminFetch<{
      id: number
      title: string
      release_kind: string | null
      released_at: string | null
      display_position: number
      cover_key: string | null
      manual_lock: boolean
      soundcloud_album_id: number | null
      tracks: Array<{
        position: number
        track: Record<string, unknown>
      }>
    }>(`/artists/${artistId}/catalog/releases/${releaseId}`),

  catalogCreateRelease: (
    artistId: number,
    body: {
      title: string
      release_kind?: string | null
      released_at?: string | null
      soundcloud_album_id?: number | null
      manual_lock?: boolean
    },
  ) =>
    adminFetch<{
      id: number
      title: string
      release_kind: string | null
      released_at: string | null
      display_position: number
      track_count: number
      cover_key: string | null
      manual_lock: boolean
      soundcloud_album_id: number | null
    }>(`/artists/${artistId}/catalog/releases`, {
      method: 'POST',
      body,
    }),

  catalogPatchRelease: (
    artistId: number,
    releaseId: number,
    body: Record<string, unknown>,
  ) =>
    adminFetch<{
      id: number
      title: string
      release_kind: string | null
      released_at: string | null
      display_position: number
      track_count: number
      cover_key: string | null
      manual_lock: boolean
      soundcloud_album_id: number | null
    }>(
      `/artists/${artistId}/catalog/releases/${releaseId}`,
      {
        method: 'PATCH',
        body,
      },
    ),

  catalogUploadReleaseCover: (
    artistId: number,
    releaseId: number,
    file: File,
  ) => {
    const fd = new FormData()
    fd.append('file', file)
    return adminFetch<{
      id: number
      title: string
      release_kind: string | null
      released_at: string | null
      display_position: number
      track_count: number
      cover_key: string | null
      manual_lock: boolean
      soundcloud_album_id: number | null
    }>(
      `/artists/${artistId}/catalog/releases/${releaseId}/cover`,
      { method: 'POST', body: fd },
    )
  },

  updateTrackMetadata: (
    trackId: number,
    body: {
      title?: string
      artist?: string | null
      description?: string | null
      genre?: string | null
      is_public?: boolean
      sc_url?: string | null
      source_url?: string | null
      canonical_source_url?: string | null
    },
  ) =>
    adminFetch<Record<string, unknown>>(`/tracks/${trackId}`, {
      method: 'PATCH',
      body,
    }),

  uploadTrackCover: (trackId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return adminFetch<Record<string, unknown>>(
      `/tracks/${trackId}/cover`,
      { method: 'POST', body: fd },
    )
  },

  catalogDeleteRelease: (artistId: number, releaseId: number) =>
    adminFetch<void>(
      `/artists/${artistId}/catalog/releases/${releaseId}`,
      { method: 'DELETE' },
    ),

  catalogReorderReleases: (
    artistId: number,
    orderedReleaseIds: number[],
  ) =>
    adminFetch<void>(
      `/artists/${artistId}/catalog/release-display-order`,
      {
        method: 'PUT',
        body: {
          ordered_release_ids: orderedReleaseIds,
        },
      },
    ),

  catalogSetReleaseTracks: (
    artistId: number,
    releaseId: number,
    trackIds: number[],
  ) =>
    adminFetch<{
      id: number
      title: string
      tracks: Array<{
        position: number
        track: Record<string, unknown>
      }>
    }>(
      `/artists/${artistId}/catalog/releases/${releaseId}/tracks`,
      {
        method: 'PUT',
        body: { track_ids: trackIds },
      },
    ),

  catalogSearchTracks: (
    artistId: number,
    params: { search?: string; page?: number; size?: number },
  ) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>(`/artists/${artistId}/catalog/tracks/search`, {
      query: params,
    }),

  catalogSyncFull: (artistId: number) =>
    adminFetch<{ queued: boolean; task: string; job_id?: string | null }>(
      `/artists/${artistId}/catalog/sync`,
      { method: 'POST', body: {} },
    ),
  catalogForceStationSync: (artistId: number) =>
    adminFetch<{ queued: boolean; task: string; job_id?: string | null }>(
      `/artists/${artistId}/catalog/station/force-sync`,
      { method: 'POST', body: {} },
    ),
  catalogSyncBatch: (artistIds: number[]) =>
    adminFetch<{
      queued: number
      job_ids: Record<string, string | null>
      errors: Array<{ artist_id: number; detail: string }>
    }>('/artists/catalog/sync-batch', {
      method: 'POST',
      body: { artist_ids: artistIds },
    }),

  artistLyricsSyncBatch: (artistIds: number[]) =>
    adminFetch<{
      queued: number
      job_ids: Record<string, string | null>
      errors: Array<{ artist_id: number; detail: string }>
    }>('/artists/lyrics/sync-batch', {
      method: 'POST',
      body: {
        artist_ids: artistIds,
        with_sync: true,
        include_existing_text: true,
      },
    }),

  catalogSyncRelease: (artistId: number, releaseId: number) =>
    adminFetch<{
      queued: boolean
      task: string
      job_id?: string | null
      soundcloud_album_id: number
    }>(
      `/artists/${artistId}/catalog/releases/${releaseId}/sync`,
      { method: 'POST', body: {} },
    ),

  // --- Track Context ---

  getTrackContext: (trackId: number) =>
    adminFetch<{
      track_id: number
      content: string | null
      status: string
      fetched_at: string | null
    }>(`/tracks/${trackId}/context`),

  setTrackContext: (trackId: number, content: string) =>
    adminFetch<{
      track_id: number
      content: string | null
      status: string
      fetched_at: string | null
    }>(`/tracks/${trackId}/context`, {
      method: 'PATCH',
      body: { content },
    }),

  clearTrackContext: (trackId: number) =>
    adminFetch<{
      track_id: number
      content: string | null
      status: string
      fetched_at: string | null
    }>(`/tracks/${trackId}/context`, {
      method: 'DELETE',
    }),

  getTrackPrompt: (trackId: number) =>
    adminFetch<{ prompt: string; language: string }>(
      `/tracks/${trackId}/prompt`,
    ),

  batchPrompt: (trackIds: number[]) =>
    adminFetch<{ prompt: string; track_count: number }>(
      '/tracks/context/batch-prompt',
      { method: 'POST', body: { track_ids: trackIds } },
    ),

  batchImport: (rawResponse: string) =>
    adminFetch<{ imported: number; errors: string[] }>(
      '/tracks/context/batch-import',
      { method: 'POST', body: { raw_response: rawResponse } },
    ),

  batchLyricsPrompt: (body: {
    track_ids?: number[]
    search?: string
    only_without_lyrics?: boolean
    limit?: number
  }) =>
    adminFetch<{ prompt: string; track_count: number }>(
      '/tracks/lyrics/batch-prompt',
      { method: 'POST', body },
    ),

  batchLyricsImport: (
    rawResponse: string,
    skipExisting: boolean = true,
  ) =>
    adminFetch<{ imported: number; errors: string[] }>(
      '/tracks/lyrics/batch-import',
      {
        method: 'POST',
        body: {
          raw_response: rawResponse,
          skip_existing: skipExisting,
        },
      },
    ),

  lyricsTimecodeSyncQueue: (params?: {
    mine?: boolean
    since_hours?: number
  }) =>
    adminFetch<{
      filters: {
        requested_by_user_id: number | null
        since: string | null
      }
      candidate_count: number
      counts: {
        queued: number
        running: number
        recent_terminal: number
      }
      running: LyricsTimecodeSyncJob | null
      next: LyricsTimecodeSyncJob | null
      queued: LyricsTimecodeSyncJob[]
      recent: LyricsTimecodeSyncJob[]
    }>('/tracks/lyrics-timecode-sync/queue', { query: params }),

  lyricsTimecodeSyncCancelJob: (jobId: string) =>
    adminFetch<{ status: string; job_status?: string }>(
      `/tracks/lyrics-timecode-sync/jobs/${encodeURIComponent(jobId)}/cancel`,
      { method: 'POST', body: {} },
    ),

  lyricsTimecodeSyncEnqueue: (body: {
    track_ids?: number[]
    enqueue_all_unsynced?: boolean
    limit?: number
  }) =>
    adminFetch<{
      requested: number
      enqueued: number
      skipped: number
      job_ids: string[]
    }>('/tracks/lyrics-timecode-sync/enqueue', {
      method: 'POST',
      body,
    }),

  lyricsTimecodeSyncSetPriority: (
    jobId: string,
    body: { queue_priority?: number; bump_next?: boolean },
  ) =>
    adminFetch<LyricsTimecodeSyncJob>(
      `/tracks/lyrics-timecode-sync/jobs/${encodeURIComponent(jobId)}/priority`,
      { method: 'PATCH', body },
    ),

  batchGenreMoodPrompt: (body: {
    track_ids?: number[]
    search?: string
    only_without_genre?: boolean
    limit?: number
  }) =>
    adminFetch<{ prompt: string; track_count: number }>(
      '/tracks/genre-mood/batch-prompt',
      { method: 'POST', body },
    ),

  batchGenreMoodImport: (
    rawResponse: string,
    overwriteGenre: boolean = false,
  ) =>
    adminFetch<{ imported: number; errors: string[] }>(
      '/tracks/genre-mood/batch-import',
      {
        method: 'POST',
        body: {
          raw_response: rawResponse,
          overwrite_genre: overwriteGenre,
        },
      },
    ),

  artistSupplementalBatchPrompt: (artistIds: number[]) =>
    adminFetch<{ prompt: string; artist_count: number }>(
      '/artists/supplemental/batch-prompt',
      {
        method: 'POST',
        body: { artist_ids: artistIds },
      },
    ),

  artistSupplementalBatchImport: (rawResponse: string) =>
    adminFetch<{ imported: number; errors: string[] }>(
      '/artists/supplemental/batch-import',
      {
        method: 'POST',
        body: { raw_response: rawResponse },
      },
    ),

  artistDiscography: (artistId: number) =>
    adminFetch<
      {
        title: string
        year: number | null
        type: string | null
        url: string | null
      }[]
    >(`/artists/${artistId}/discography`),

  artistDiscographySave: (
    artistId: number,
    items: {
      title: string
      year: number | null
      type: string | null
      url: string | null
    }[],
  ) =>
    adminFetch<
      {
        title: string
        year: number | null
        type: string | null
        url: string | null
      }[]
    >(`/artists/${artistId}/discography`, {
      method: 'PUT',
      body: items,
    }),

  listExperiments: () =>
    adminFetch<
      {
        id: number
        key: string
        arms: Record<string, number>
        status: string
        description: string | null
        created_at: string
        updated_at: string
      }[]
    >(`/recsys/experiments`),

  createExperiment: (payload: {
    key: string
    arms: Record<string, number>
    description?: string | null
  }) =>
    adminFetch<{
      id: number
      key: string
      arms: Record<string, number>
      status: string
      description: string | null
      created_at: string
      updated_at: string
    }>(`/recsys/experiments`, {
      method: 'POST',
      body: payload,
    }),

  updateExperiment: (
    id: number,
    payload: {
      arms?: Record<string, number>
      status?: string
      description?: string | null
    },
  ) =>
    adminFetch<{
      id: number
      key: string
      arms: Record<string, number>
      status: string
      description: string | null
      created_at: string
      updated_at: string
    }>(`/recsys/experiments/${id}`, {
      method: 'PATCH',
      body: payload,
    }),

  deleteExperiment: (id: number) =>
    adminFetch<{ deleted: boolean }>(
      `/recsys/experiments/${id}`,
      { method: 'DELETE' },
    ),

  experimentStats: (id: number) =>
    adminFetch<{
      experiment: {
        id: number
        key: string
        arms: Record<string, number>
        status: string
        description: string | null
        created_at: string
        updated_at: string
      }
      assignment_counts: Record<string, number>
      arm_outcomes: {
        arm: string
        impressions: number
        completed: number
        skipped: number
        completion_rate: number
        skip_rate: number
      }[]
      significance: {
        arm_a: string
        arm_b: string
        lift: number
        z: number
        p_value_two_sided: number
        sample_too_small: boolean
        significant: boolean
      } | null
    }>(`/recsys/experiments/${id}/stats`),

  backfillEmbeddings: (limit: number) =>
    adminFetch<{
      enqueued_count: number
      track_ids: number[]
    }>(
      `/recsys/embeddings/backfill?limit=${limit}`,
      { method: 'POST', body: {} },
    ),

  antivirusStatus: () =>
    adminFetch<{
      reachable: boolean
      mode: string
      version: string | null
      host?: string
      port?: number
      error?: string
      note?: string
    }>('/antivirus/status'),

  antivirusStats: () =>
    adminFetch<{
      total: number
      clean: number
      infected: number
      error: number
      skipped: number
    }>('/antivirus/stats'),

  antivirusEvents: (params?: {
    limit?: number
    offset?: number
    verdict?: string
  }) =>
    adminFetch<{
      total: number
      items: {
        id: number
        filename: string
        file_size: number | null
        verdict: string
        threat_name: string | null
        scan_mode: string
        scanned_at: string
      }[]
    }>('/antivirus/events', { query: params }),

  setCatalogSyncEnabled: (
    artistId: number,
    enabled: boolean,
  ) =>
    adminFetch<{ artist_id: number; catalog_sync_enabled: boolean }>(
      `/artists/${artistId}/catalog-sync-enabled`,
      { method: 'PATCH', body: { enabled } },
    ),

  importArtistByScUrl: (url: string) =>
    adminFetch<{
      artist_id: number
      artist_name: string
      created: boolean
      catalog_sync_enabled: boolean
      queued: boolean
      job_id?: string | null
    }>('/artists/import-by-sc-url', {
      method: 'POST',
      body: { url },
    }),
}
