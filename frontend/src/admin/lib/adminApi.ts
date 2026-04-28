import { useAdminAuth } from '../store/adminAuthStore'
import { ensureCsrf, readCsrfCookie } from './csrf'

const BASE = '/api/v1/admin'

export class AdminApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
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
  const url = new URL(
    `${BASE}${path}`,
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

async function rawRequest(
  path: string,
  opts: RequestOptions,
): Promise<Response> {
  const method = (opts.method || 'GET').toUpperCase()
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(opts.headers || {}),
  }
  if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (
    method !== 'GET' &&
    method !== 'HEAD' &&
    method !== 'OPTIONS'
  ) {
    const csrf = await ensureCsrf()
    if (csrf) headers['X-Admin-CSRF'] = csrf
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
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      detail =
        body?.detail ||
        body?.message ||
        JSON.stringify(body)
    } catch {
      try {
        detail = await response.text()
      } catch {
        // keep default
      }
    }
    throw new AdminApiError(response.status, detail)
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
  requestDeviceApproval: (deviceId: number) =>
    adminFetch<{ detail: string }>(
      '/auth/devices/request-approval',
      {
        method: 'POST',
        body: { device_id: deviceId },
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
  servicesHealth: () =>
    adminFetch<Record<string, unknown>>(
      '/system/services',
    ),
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
  listTracks: (params: {
    page?: number
    size?: number
    is_active?: boolean
    search?: string
  }) =>
    adminFetch<{
      items: Array<Record<string, unknown>>
      total: number
      page: number
      size: number
    }>('/tracks', { query: params }),
  deleteTrack: (trackId: number) =>
    adminFetch<void>(`/tracks/${trackId}`, {
      method: 'DELETE',
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
}
