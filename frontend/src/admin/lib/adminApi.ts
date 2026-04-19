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

async function withRefresh(
  doRequest: () => Promise<Response>,
): Promise<Response> {
  const response = await doRequest()
  if (response.status !== 401) {
    return response
  }
  if (
    useAdminAuth.getState().accessToken === null
  ) {
    return response
  }
  const refreshed = await rawRequest(
    '/auth/refresh',
    { method: 'POST', body: {} },
  )
  if (refreshed.status !== 200) {
    useAdminAuth.getState().reset()
    return response
  }
  const data = (await refreshed.json()) as {
    access_token: string
    expires_in: number
  }
  useAdminAuth
    .getState()
    .setSession(
      data.access_token,
      data.expires_in,
    )
  return doRequest()
}

export async function adminFetch<T = unknown>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const response = await withRefresh(() =>
    rawRequest(path, opts),
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
  refresh: () =>
    adminFetch<{
      access_token: string
      refresh_token: string
      expires_in: number
    }>('/auth/refresh', {
      method: 'POST',
      body: {},
    }),
  logout: () =>
    adminFetch<{ detail: string }>('/auth/logout', {
      method: 'POST',
      body: {},
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
}
