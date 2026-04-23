import {
  getInternalUserId,
  setInternalUserId,
  setIsAdmin,
} from '@/lib/telegram'
import type {
  AppNotification,
  ArtistDetail,
  ArtistEnrichStatusResponse,
  ArtistEnrichWatchResponse,
  ArtistSupplementalResponse,
  AuthorProfile,
  AvatarResponse,
  ChatListItem,
  ChatMessage,
  ComplaintCreate,
  ComplaintSubmitResponse,
  DislikeToggleResponse,
  EmailVerifyResponse,
  FollowToggleResponse,
  ImportJobResponse,
  LikeToggleResponse,
  LyricsAutoResponse,
  LyricsAutoStatusResponse,
  LyricsResponse,
  Playlist,
  PlaylistWithTracks,
  SCSearchResult,
  ShareResponse,
  StreamResponse,
  SyncedLine,
  TokenResponse,
  Track,
  TrackCardResponse,
  TrackComment,
  TrackInfoResponse,
  TrackListResponse,
  TrackUploadResponse,
  TwoFASetupResponse,
  UserLikesResponse,
  UserResponse,
  UserStatsResponse,
} from '@/types/api'

let accessToken: string | null = null
let onUnauthorized: (() => void) | null = null
let onAccountBlocked:
  | ((reason?: string | null) => void)
  | null = null
const AUTH_TOKEN_KEY = 'auth-token'

function decodeJwtPayload(
  token: string,
): Record<string, unknown> | null {
  try {
    const [, payload] = token.split('.')
    if (!payload) return null
    const base64 = payload
      .replace(/-/g, '+')
      .replace(/_/g, '/')
    const padded = base64.padEnd(
      base64.length +
        ((4 - (base64.length % 4)) % 4),
      '=',
    )
    const decoded = atob(padded)
    return JSON.parse(decoded) as Record<
      string,
      unknown
    >
  } catch {
    return null
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token)
  const exp = Number(payload?.exp)
  if (!Number.isFinite(exp)) return false
  const now = Math.floor(Date.now() / 1000)
  return exp <= now
}

function getTokenUserId(
  token: string,
): number | null {
  const payload = decodeJwtPayload(token)
  const sub = Number(payload?.sub)
  return Number.isFinite(sub) ? sub : null
}

function persistToken(
  token: string | null,
) {
  try {
    if (token) {
      localStorage.setItem(
        AUTH_TOKEN_KEY,
        token,
      )
    } else {
      localStorage.removeItem(
        AUTH_TOKEN_KEY,
      )
    }
  } catch {}
}

function loadStoredToken():
  | string
  | null {
  try {
    const token = localStorage.getItem(
      AUTH_TOKEN_KEY,
    )
    if (!token) return null
    if (isTokenExpired(token)) {
      localStorage.removeItem(
        AUTH_TOKEN_KEY,
      )
      return null
    }
    return token
  } catch {
    return null
  }
}

async function readApiErrorMessage(
  res: Response,
): Promise<string> {
  const ct = res.headers.get('content-type') || ''
  if (!ct.includes('application/json')) {
    return String(res.status)
  }
  try {
    const body = (await res.json()) as {
      detail?: unknown
    }
    if (typeof body?.detail === 'string') {
      return body.detail
    }
    if (Array.isArray(body?.detail)) {
      const parts: string[] = []
      for (const d of body.detail) {
        if (
          d &&
          typeof d === 'object' &&
          'msg' in d &&
          typeof (d as { msg: string }).msg === 'string'
        ) {
          parts.push((d as { msg: string }).msg)
        }
      }
      if (parts.length) return parts.join('; ')
    }
  } catch {
    /* not JSON or partial body */
  }
  return String(res.status)
}

/** API errors from `request` carry server `detail` in `message` when available. */
export function getApiErrorMessage(
  err: unknown,
  fallback: string,
): string {
  if (!(err instanceof Error) || !err.message?.trim()) {
    return fallback
  }
  const m = err.message.trim()
  if (
    m.length <= 3 &&
    /^[1-5]\d{2}$/.test(m)
  ) {
    return fallback
  }
  return m
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers)
  const sentWithAuth =
    Boolean(accessToken) ||
    headers.has('Authorization')
  if (accessToken && !headers.has('Authorization')) {
    headers.set(
      'Authorization',
      `Bearer ${accessToken}`,
    )
  }

  try {
    const res = await fetch(path, {
      ...opts,
      headers,
    })
    const accountStatus = res.headers.get(
      'X-Account-Status',
    )
    const isBanned =
      accountStatus === 'banned' ||
      accountStatus === 'blocked'
    if (res.status === 401 && sentWithAuth) {
      console.error(
        `[API] 401 Unauthorized: ${path}`,
      )
      accessToken = null
      persistToken(null)
      if (isBanned) {
        onAccountBlocked?.(
          res.headers.get('X-Account-Reason'),
        )
      } else {
        onUnauthorized?.()
      }
    } else if (isBanned) {
      onAccountBlocked?.(
        res.headers.get('X-Account-Reason'),
      )
    }
    if (!res.ok) {
      const message = await readApiErrorMessage(res)
      throw new Error(message)
    }
    if (res.status === 204) return null as T
    return res.json() as Promise<T>
  } catch (err) {
    console.error(
      `[API] Fetch error for ${path}:`,
      err,
    )
    throw err
  }
}

export const api = {
  getTracks(params?: { q?: string; size?: number; page?: number }): Promise<TrackListResponse> {
    const sp = new URLSearchParams()
    if (params?.q) sp.set('q', params.q)
    if (params?.size) sp.set('size', String(params.size))
    if (params?.page) sp.set('page', String(params.page))
    const query = sp.toString() ? `?${sp}` : ''
    return request(`/api/v1/tracks${query}`)
  },

  getMyTracks(page = 1, size = 50): Promise<TrackListResponse> {
    return request(`/api/v1/tracks/my?page=${page}&size=${size}`)
  },

  getMyLibrary(
    page = 1,
    size = 50,
    playableOnly = false,
  ): Promise<TrackListResponse> {
    const params = new URLSearchParams({
      page: String(page),
      size: String(size),
    })
    if (playableOnly) {
      params.set('playable_only', 'true')
    }
    return request(
      `/api/v1/users/me/library?${params.toString()}`,
    )
  },

  getListenHistory(
    limit: number = 50,
  ): Promise<TrackListResponse> {
    return request(
      `/api/v1/users/me/listen-history?limit=${limit}`,
    )
  },

  getTrack(id: number): Promise<Track> {
    return request(`/api/v1/tracks/${id}`)
  },

  getStream(id: number): Promise<StreamResponse> {
    return request(`/api/v1/tracks/${id}/stream`)
  },

  getAdjacentTracks(
    trackId: number,
  ): Promise<{
    prev_id: number | null
    next_id: number | null
  }> {
    return request(
      `/api/v1/tracks/${trackId}/adjacent`,
    )
  },

  getTrackQueue(
    trackId: number,
    count = 3,
  ): Promise<{ next_tracks: Track[] }> {
    return request(
      `/api/v1/tracks/${trackId}/queue?count=${count}`,
    )
  },

  getGenres(): Promise<string[]> {
    return request('/api/v1/tracks/genres')
  },

  postPlay(id: number): Promise<void> {
    return request(`/api/v1/tracks/${id}/play`, { method: 'POST' })
  },

  uploadTrack(formData: FormData): Promise<TrackUploadResponse> {
    return request('/api/v1/tracks/upload', { method: 'POST', body: formData })
  },

  updateTrack(trackId: number, data: { is_public?: boolean }): Promise<Track> {
    return request(`/api/v1/tracks/${trackId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  deleteTrack(trackId: number): Promise<void> {
    return request(`/api/v1/tracks/${trackId}`, {
      method: 'DELETE',
    })
  },

  searchSoundCloud(q: string, limit = 20): Promise<SCSearchResult[]> {
    return request(`/api/v1/soundcloud/search?q=${encodeURIComponent(q)}&limit=${limit}`)
  },

  importSCTrack(sc_url: string, is_public = true): Promise<Track> {
    return request('/api/v1/soundcloud/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sc_url, is_public }),
    })
  },

  toggleLike(userId: number, trackId: number): Promise<LikeToggleResponse> {
    return request(`/api/v1/likes/${userId}/${trackId}`, { method: 'POST' })
  },

  toggleDislike(userId: number, track_id: number): Promise<DislikeToggleResponse> {
    return request(`/api/v1/dislikes/${userId}/${track_id}`, { method: 'POST' })
  },

  getLikedTracks(userId: number, page = 1, size = 20): Promise<UserLikesResponse> {
    return request(`/api/v1/likes/${userId}?page=${page}&size=${size}`)
  },

  submitComplaint(body: ComplaintCreate): Promise<ComplaintSubmitResponse> {
    return request('/api/v1/complaints', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  getPlaylists(ownerId: number): Promise<Playlist[]> {
    return request(`/api/v1/playlists?owner_id=${ownerId}`)
  },

  getPlaylist(id: number): Promise<PlaylistWithTracks> {
    return request(`/api/v1/playlists/${id}`)
  },

  createPlaylist(ownerId: number, name: string, isPublic = false): Promise<Playlist> {
    return request(`/api/v1/playlists?owner_id=${ownerId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, is_public: isPublic }),
    })
  },

  addTrackToPlaylist(
    playlistId: number,
    trackId: number,
    requesterId: number,
  ): Promise<void> {
    return request(
      `/api/v1/playlists/${playlistId}/tracks?requester_id=${requesterId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ track_id: trackId }),
      },
    )
  },

  getUserProfile(userId: number): Promise<UserResponse> {
    return request(`/api/v1/users/${userId}`)
  },

  getUserStats(userId: number): Promise<UserStatsResponse> {
    return request(`/api/v1/users/${userId}/stats`)
  },

  updateProfile(
    display_name?: string,
    locale?: string,
  ): Promise<UserResponse> {
    const body: Record<string, string> = {}
    if (display_name) body.display_name = display_name
    if (locale !== undefined) body.locale = locale
    return request('/api/v1/users/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  uploadAvatar(userId: number, formData: FormData): Promise<AvatarResponse> {
    return request(`/api/v1/users/${userId}/avatar`, {
      method: 'POST',
      body: formData,
    })
  },

  getAvatarUrl(userId: number): Promise<AvatarResponse> {
    return request(`/api/v1/users/${userId}/avatar`)
  },

  // ── Track card ────────────────────────────────────────────────────────────

  getTrackCard(trackId: number): Promise<TrackCardResponse> {
    return request(`/api/v1/tracks/${trackId}/card`)
  },

  getShareLinks(trackId: number): Promise<ShareResponse> {
    return request(`/api/v1/tracks/${trackId}/share`)
  },

  // ── Lyrics ────────────────────────────────────────────────────────────────

  getLyrics(trackId: number): Promise<LyricsResponse> {
    return request(`/api/v1/tracks/${trackId}/lyrics`)
  },

  saveLyrics(trackId: number, plainText: string): Promise<LyricsResponse> {
    return request(`/api/v1/tracks/${trackId}/lyrics`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plain_text: plainText }),
    })
  },

  saveLyricsSync(trackId: number, syncedLines: SyncedLine[]): Promise<LyricsResponse> {
    return request(`/api/v1/tracks/${trackId}/lyrics/sync`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ synced_lines: syncedLines }),
    })
  },

  deleteLyrics(trackId: number): Promise<void> {
    return request(`/api/v1/tracks/${trackId}/lyrics`, { method: 'DELETE' })
  },

  redefineLyrics(
    trackId: number,
    withSync: boolean = false,
    bypassCache: boolean = false,
  ): Promise<LyricsAutoResponse> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/redefine`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          with_sync: withSync,
          bypass_cache: bypassCache,
        }),
      },
    )
  },

  generateLyrics(
    trackId: number,
    withSync: boolean = false,
  ): Promise<LyricsAutoResponse> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/auto`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          with_sync: withSync,
        }),
      },
    )
  },

  generateLyricsDebug(
    trackId: number,
    tier: number,
  ): Promise<LyricsAutoResponse> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/debug/stage/${tier}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      },
    )
  },

  getLyricsAutoStatus(
    trackId: number,
    taskId: string,
  ): Promise<LyricsAutoStatusResponse> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/auto/status?task_id=${taskId}`,
    )
  },

  lyricsAutoEventsUrl(
    trackId: number,
    taskId: string,
  ): string {
    return `/api/v1/tracks/${trackId}/lyrics/auto/events?task_id=${encodeURIComponent(
      taskId,
    )}`
  },

  cancelLyricsGeneration(
    trackId: number,
    taskId: string,
  ): Promise<{ status: string }> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/auto/cancel?task_id=${taskId}`,
      {
        method: 'POST',
      },
    )
  },

  getAdminManifest(locale?: string): Promise<{
    capabilities: string[]
    menu: Array<{
      id: string
      label: string
      route: string
      icon?: string
      capability?: string | null
    }>
    slots: Record<
      string,
      Array<{
        id: string
        label: string
        capability: string
        icon?: string
        action: string
        confirm?: boolean
      }>
    >
    adminBundleUrl: string
    issuedAt: number
    expiresIn: number
    locale: string
  }> {
    const qs = locale ? `?locale=${encodeURIComponent(locale)}` : ''
    return request(`/api/v1/admin/manifest${qs}`)
  },

  // ── Follow ────────────────────────────────────────────────────────────────

  toggleFollow(targetUserId: number): Promise<FollowToggleResponse> {
    return request(`/api/v1/users/${targetUserId}/follow`, { method: 'POST' })
  },

  getFollowStatus(targetUserId: number): Promise<{ following: boolean }> {
    return request(`/api/v1/users/${targetUserId}/follow/status`)
  },

  // ── Author page ───────────────────────────────────────────────────────────

  getAuthorProfile(userId: number): Promise<AuthorProfile> {
    return request(`/api/v1/users/${userId}`)
  },

  getAuthorTracks(userId: number, page = 1, size = 20): Promise<TrackListResponse> {
    return request(`/api/v1/users/${userId}/tracks?page=${page}&size=${size}`)
  },

  // ── Auth ────────────────────────────────────────────────────────────────────

  async authTelegram(init_data: string): Promise<TokenResponse> {
    if (!init_data) {
      throw new Error('No Telegram initData')
    }
    const res = await request<TokenResponse>('/api/v1/auth/telegram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data }),
    })
    accessToken = res.access_token
    persistToken(accessToken)
    setInternalUserId(res.user_id)
    setIsAdmin(res.is_admin)
    return res
  },

  async authMock(user_id: number): Promise<TokenResponse> {
    const res = await request<TokenResponse>(`/api/v1/auth/mock/${user_id}`, {
      method: 'POST',
    })
    accessToken = res.access_token
    persistToken(accessToken)
    setInternalUserId(res.user_id)
    setIsAdmin(res.is_admin)
    return res
  },

  setToken(token: string | null) {
    accessToken = token
    persistToken(token)
  },

  getToken(): string | null {
    return accessToken
  },

  restoreSession():
    | {
        token: string
        userId: number
      }
    | null {
    const token = loadStoredToken()
    if (!token) {
      setInternalUserId(null)
      return null
    }
    const userId = getTokenUserId(token)
    if (userId === null) {
      persistToken(null)
      setInternalUserId(null)
      return null
    }
    const storedUserId = getInternalUserId()
    if (
      storedUserId !== null &&
      storedUserId !== userId
    ) {
      persistToken(null)
      setInternalUserId(null)
      return null
    }
    accessToken = token
    if (storedUserId === null) {
      setInternalUserId(userId)
    }
    return { token, userId }
  },

  logout() {
    accessToken = null
    persistToken(null)
    setInternalUserId(null)
    setIsAdmin(false)
  },

  setOnUnauthorized(cb: (() => void) | null) {
    onUnauthorized = cb
  },

  setOnAccountBlocked(
    cb: ((reason?: string | null) => void) | null,
  ) {
    onAccountBlocked = cb
  },

  getMyComplaints(): Promise<{
    items: Array<{
      id: number
      track_id: number
      reason: string
      reason_type: string
      is_resolved: boolean
      track_hidden?: boolean
      created_at: string
      resolution_note?: string | null
    }>
  }> {
    return request('/api/v1/users/me/complaints')
  },

  updateComplaintStatus(
    id: number,
    body: {
      action: 'accept' | 'dismiss' | 'in_progress'
      note?: string
    },
  ): Promise<{ ok: boolean }> {
    return request(
      `/api/v1/admin/complaints/${id}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      },
    )
  },

  getAuthConfig(): Promise<{
    bot_username: string
    debug?: boolean
  }> {
    return request('/api/v1/auth/config')
  },

  async verifyTelegramCode(
    code: string,
  ): Promise<TokenResponse> {
    const res = await request<TokenResponse>(
      '/api/v1/auth/verify-code',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code }),
      },
    )
    accessToken = res.access_token
    persistToken(accessToken)
    setInternalUserId(res.user_id)
    setIsAdmin(res.is_admin)
    return res
  },

  requestMagicLink(
    email: string,
  ): Promise<{ message: string }> {
    return request('/api/v1/auth/email/request', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
    })
  },

  async verifyMagicLink(
    token: string,
    signal?: AbortSignal,
  ): Promise<EmailVerifyResponse> {
    const res =
      await request<EmailVerifyResponse>(
        '/api/v1/auth/email/verify',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ token }),
          signal,
        },
      )
    if (
      res.access_token &&
      res.user_id &&
      !res.requires_2fa
    ) {
      accessToken = res.access_token
      persistToken(accessToken)
      setInternalUserId(res.user_id)
      setIsAdmin(res.is_admin)
    }
    return res
  },

  async verify2FA(
    sessionToken: string,
    code: string,
  ): Promise<EmailVerifyResponse> {
    const res =
      await request<EmailVerifyResponse>(
        '/api/v1/auth/2fa/verify',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_token: sessionToken,
            code,
          }),
        },
      )
    if (res.access_token && res.user_id) {
      accessToken = res.access_token
      persistToken(accessToken)
      setInternalUserId(res.user_id)
      setIsAdmin(res.is_admin)
    }
    return res
  },

  async verify2FABackup(
    sessionToken: string,
    backupCode: string,
  ): Promise<EmailVerifyResponse> {
    const res =
      await request<EmailVerifyResponse>(
        '/api/v1/auth/2fa/verify',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_token: sessionToken,
            backup_code: backupCode,
          }),
        },
      )
    if (res.access_token && res.user_id) {
      accessToken = res.access_token
      persistToken(accessToken)
      setInternalUserId(res.user_id)
      setIsAdmin(res.is_admin)
    }
    return res
  },

  request2FAEmailFallback(
    sessionToken: string,
  ): Promise<{ status: string }> {
    return request(
      '/api/v1/auth/2fa/email-fallback',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_token: sessionToken,
        }),
      },
    )
  },

  async verify2FAEmailFallback(
    sessionToken: string,
    code: string,
  ): Promise<EmailVerifyResponse> {
    const res =
      await request<EmailVerifyResponse>(
        '/api/v1/auth/2fa/email-fallback/verify',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_token: sessionToken,
            code,
          }),
        },
      )
    if (res.access_token && res.user_id) {
      accessToken = res.access_token
      persistToken(accessToken)
      setInternalUserId(res.user_id)
      setIsAdmin(res.is_admin)
    }
    return res
  },

  setup2FA(): Promise<TwoFASetupResponse> {
    return request('/api/v1/auth/2fa/setup', {
      method: 'POST',
    })
  },

  confirm2FA(
    code: string,
  ): Promise<{ status: string }> {
    return request('/api/v1/auth/2fa/confirm', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code }),
    })
  },

  disable2FA(
    code: string,
  ): Promise<{ status: string }> {
    return request('/api/v1/auth/2fa', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code }),
    })
  },

  getLinkStatus(): Promise<{
    telegram_linked: boolean
    email_linked: boolean
    email: string | null
    telegram_username: string | null
  }> {
    return request(
      '/api/v1/account/link-status',
    )
  },

  requestLinkEmail(
    email: string,
  ): Promise<{ status: string }> {
    return request(
      '/api/v1/account/link/email',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      },
    )
  },

  verifyLinkEmail(
    token: string,
  ): Promise<{ status: string }> {
    return request(
      '/api/v1/account/link/email/verify',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token }),
      },
    )
  },

  generateLinkTelegramCode(): Promise<{
    code: string
    bot_username: string
    deep_link: string
  }> {
    return request(
      '/api/v1/account/link/telegram/generate-code',
      { method: 'POST' },
    )
  },

  mergeAccounts(
    sourceAccountToken: string,
  ): Promise<{ status: string }> {
    return request('/api/v1/account/merge', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        source_account_token:
          sourceAccountToken,
      }),
    })
  },

  startTelegramImport(): Promise<ImportJobResponse> {
    return request('/api/v1/import/telegram', {
      method: 'POST',
    })
  },

  startYandexMusicImport(
    url: string,
  ): Promise<ImportJobResponse> {
    return request('/api/v1/import/yandex_music', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
  },

  startImportJob(
    jobId: number,
    trackIndices: number[],
  ): Promise<ImportJobResponse> {
    return request(`/api/v1/import/${jobId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        track_indices: trackIndices,
      }),
    })
  },

  getImportStatus(jobId: number): Promise<ImportJobResponse> {
    return request(`/api/v1/import/${jobId}/status`)
  },

  getActiveImport(): Promise<ImportJobResponse | null> {
    return request('/api/v1/import/active')
  },

  cancelImport(jobId: number): Promise<ImportJobResponse> {
    return request(`/api/v1/import/${jobId}/cancel`, {
      method: 'POST',
    })
  },

  uploadTrackCover(
    trackId: number,
    formData: FormData,
  ): Promise<Track> {
    return request(
      `/api/v1/tracks/${trackId}/cover`,
      { method: 'POST', body: formData },
    )
  },

  regenerateTrackCover(
    trackId: number,
  ): Promise<Track> {
    return request(
      `/api/v1/tracks/${trackId}/cover/generate`,
      { method: 'POST' },
    )
  },

  restoreTrackCover(
    trackId: number,
  ): Promise<Track> {
    return request(
      `/api/v1/tracks/${trackId}/cover/restore`,
      { method: 'POST' },
    )
  },

  uploadTrackVideo(
    trackId: number,
    formData: FormData,
  ): Promise<Track> {
    return request(
      `/api/v1/tracks/${trackId}/video`,
      { method: 'POST', body: formData },
    )
  },

  deleteTrackVideo(
    trackId: number,
  ): Promise<void> {
    return request(
      `/api/v1/tracks/${trackId}/video`,
      { method: 'DELETE' },
    )
  },

  getEqSettings(): Promise<{
    preset: string | null
    bands: number[]
  }> {
    return request('/api/v1/users/me/eq')
  },

  saveEqSettings(data: {
    preset: string | null
    bands: number[]
  }): Promise<void> {
    return request('/api/v1/users/me/eq', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
  },

  // ── Chats ──────────────────────────────────────────

  createDM(targetUserId: number): Promise<{ conversation: { id: number } }> {
    return request('/api/v1/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_user_id: targetUserId }),
    })
  },

  createGroup(title: string, memberIds: number[]): Promise<{ conversation: { id: number } }> {
    return request('/api/v1/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, member_ids: memberIds }),
    })
  },

  listChats(): Promise<ChatListItem[]> {
    return request('/api/v1/chats')
  },

  searchUsers(q: string, limit = 20): Promise<{
    id: number
    username: string | null
    first_name: string
    last_name: string | null
    display_name: string | null
    avatar_key: string | null
  }[]> {
    return request(`/api/v1/chats/search-users?q=${encodeURIComponent(q)}&limit=${limit}`)
  },

  getSavedChat(): Promise<{ conversation: { id: number } }> {
    return request('/api/v1/chats/saved')
  },

  pinChat(convId: number): Promise<void> {
    return request(`/api/v1/chats/${convId}/pin`, { method: 'POST' })
  },

  unpinChat(convId: number): Promise<void> {
    return request(`/api/v1/chats/${convId}/pin`, { method: 'DELETE' })
  },

  // ── Messages ───────────────────────────────────────

  getMessages(convId: number, cursor?: number, limit = 20): Promise<ChatMessage[]> {
    const sp = new URLSearchParams()
    if (cursor != null) sp.set('cursor', String(cursor))
    sp.set('limit', String(limit))
    return request(`/api/v1/chats/${convId}/messages?${sp}`)
  },

  sendMessage(convId: number, content: string, opts?: {
    type?: string
    reply_to_id?: number
    shared_track_id?: number
  }): Promise<ChatMessage> {
    return request(`/api/v1/chats/${convId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, ...opts }),
    })
  },

  postActivity(
    convId: number,
    activity: string,
  ): Promise<void> {
    return request(
      `/api/v1/chats/${convId}/activity`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ activity }),
      },
    )
  },

  getActivity(convId: number): Promise<{
    activities: {
      activity: string
      user_id: number
      ts: number
    }[]
  }> {
    return request(
      `/api/v1/chats/${convId}/activity`,
    )
  },

  deleteMessage(messageId: number): Promise<void> {
    return request(`/api/v1/messages/${messageId}`, { method: 'DELETE' })
  },

  addReaction(messageId: number, reactionType: string): Promise<void> {
    return request(`/api/v1/messages/${messageId}/reactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reaction_type: reactionType }),
    })
  },

  removeReaction(messageId: number, reactionType: string): Promise<void> {
    return request(`/api/v1/messages/${messageId}/reactions/${reactionType}`, { method: 'DELETE' })
  },

  markRead(convId: number, messageId: number): Promise<void> {
    return request(`/api/v1/chats/${convId}/messages/read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId }),
    })
  },

  sendPhoto(convId: number, formData: FormData, signal?: AbortSignal): Promise<ChatMessage> {
    return request(`/api/v1/chats/${convId}/messages/photo`, {
      method: 'POST',
      body: formData,
      signal,
    })
  },

  sendVoice(convId: number, formData: FormData): Promise<ChatMessage> {
    return request(`/api/v1/chats/${convId}/messages/voice`, {
      method: 'POST',
      body: formData,
    })
  },

  // ── Comments ───────────────────────────────────────

  addComment(trackId: number, text: string): Promise<TrackComment> {
    return request(`/api/v1/tracks/${trackId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
  },

  getComments(trackId: number, cursor?: number, limit = 20): Promise<TrackComment[]> {
    const sp = new URLSearchParams()
    if (cursor != null) sp.set('cursor', String(cursor))
    sp.set('limit', String(limit))
    return request(`/api/v1/tracks/${trackId}/comments?${sp}`)
  },

  deleteComment(commentId: number): Promise<void> {
    return request(`/api/v1/comments/${commentId}`, { method: 'DELETE' })
  },

  pinComment(commentId: number): Promise<void> {
    return request(`/api/v1/comments/${commentId}/pin`, { method: 'POST' })
  },

  unpinComment(commentId: number): Promise<void> {
    return request(`/api/v1/comments/${commentId}/pin`, { method: 'DELETE' })
  },

  hideComment(commentId: number): Promise<void> {
    return request(`/api/v1/comments/${commentId}/hide`, { method: 'POST' })
  },

  hideCommentForMe(commentId: number): Promise<void> {
    return request(`/api/v1/comments/${commentId}/hide-for-me`, { method: 'POST' })
  },

  voteComment(commentId: number, isLike: boolean): Promise<void> {
    return request(`/api/v1/comments/${commentId}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_like: isLike }),
    })
  },

  removeCommentVote(commentId: number): Promise<void> {
    return request(`/api/v1/comments/${commentId}/vote`, { method: 'DELETE' })
  },

  // ── Blocks ─────────────────────────────────────────

  blockUser(userId: number): Promise<void> {
    return request(`/api/v1/users/${userId}/block`, { method: 'POST' })
  },

  unblockUser(userId: number): Promise<void> {
    return request(`/api/v1/users/${userId}/block`, { method: 'DELETE' })
  },

  listBlocks(): Promise<{ blocked_user_ids: number[] }> {
    return request('/api/v1/blocks')
  },

  // ── Notifications ──────────────────────────────────

  getNotifications(cursor?: number, limit = 20): Promise<AppNotification[]> {
    const sp = new URLSearchParams()
    if (cursor) sp.set('cursor', String(cursor))
    sp.set('limit', String(limit))
    return request(`/api/v1/notifications?${sp}`)
  },

  getUnreadCount(): Promise<{ count: number }> {
    return request('/api/v1/notifications/unread-count')
  },

  markNotificationRead(notificationId: number): Promise<void> {
    return request('/api/v1/notifications/read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notification_id: notificationId }),
    })
  },

  markAllNotificationsRead(): Promise<void> {
    return request('/api/v1/notifications/read-all', { method: 'POST' })
  },

  // ── Presence ───────────────────────────────────────

  getUserPresence(userId: number): Promise<{
    user_id: number
    status: string
    last_seen: number
  }> {
    return request(`/api/v1/users/${userId}/presence`)
  },

  getChatPresence(convId: number): Promise<{
    conversation_id: number
    members: Record<string, { status: string; last_seen: number }>
  }> {
    return request(`/api/v1/chats/${convId}/presence`)
  },

  // ── Onboarding ──────────────────────────────────

  getOnboardingStatus(): Promise<{
    onboarding_completed: boolean
    calibration_completed: boolean
    preferred_genres: string[] | null
    preferred_moods: string[] | null
  }> {
    return request('/api/v1/onboarding/status')
  },

  getOnboardingGenres(): Promise<string[]> {
    return request('/api/v1/onboarding/genres')
  },

  getOnboardingArtists(genres?: string[]): Promise<{ id: number; name: string; image_key: string | null }[]> {
    const params = genres?.length ? `?genres=${genres.join(',')}` : ''
    return request(`/api/v1/onboarding/artists${params}`)
  },

  saveOnboardingPreferences(data: {
    genres: string[]
    artist_ids: number[]
    moods: string[]
  }): Promise<void> {
    return request('/api/v1/onboarding/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  getCalibrationTracks(): Promise<Track[]> {
    return request('/api/v1/onboarding/calibration')
  },

  saveCalibration(items: { track_id: number; liked: boolean }[]): Promise<void> {
    return request('/api/v1/onboarding/calibration', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    })
  },

  completeOnboarding(): Promise<void> {
    return request('/api/v1/onboarding/complete', { method: 'POST' })
  },

  // ── Signals ─────────────────────────────────────

  recordListen(data: {
    track_id: number
    duration_listened: number
    total_duration: number | null
    source_context?: string
  }): Promise<void> {
    return request('/api/v1/signals/listen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  recordSearchClick(data: {
    query: string
    results_count?: number
    clicked_track_id?: number
  }): Promise<void> {
    return request('/api/v1/signals/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  // ── Recommendations ─────────────────────────────

  getHomeRecommendations(): Promise<{
    sections: { title: string; section_type: string; tracks: Track[] }[]
    maturity: string
  }> {
    return request('/api/v1/recommendations/home')
  },

  getSimilarTracks(trackId: number): Promise<{ seed_track_id: number; tracks: Track[] }> {
    return request(`/api/v1/recommendations/similar/${trackId}`)
  },

  getDailyMix(): Promise<{ tracks: Track[]; generated_at: string }> {
    return request('/api/v1/recommendations/daily-mix')
  },

  getRadio(seedTrackId: number, queueSize?: number): Promise<{ seed_type: string; seed_id: string; tracks: Track[] }> {
    const qs = queueSize ? `&queue_size=${queueSize}` : ''
    return request(`/api/v1/recommendations/radio?seed_track_id=${seedTrackId}${qs}`)
  },

  // ── Artists ─────────────────────────────────────

  getArtists(q?: string): Promise<{ items: { id: number; name: string; image_key: string | null; source: string; bio: string | null; created_at: string }[]; total: number }> {
    const qs = q ? `?q=${encodeURIComponent(q)}` : ''
    return request(`/api/v1/artists${qs}`)
  },

  getArtist(artistId: number): Promise<ArtistDetail> {
    return request(`/api/v1/artists/${artistId}`)
  },

  getArtistTracks(artistId: number, page?: number): Promise<TrackListResponse> {
    const p = page || 1
    return request(`/api/v1/artists/${artistId}/tracks?page=${p}`)
  },

  enrichArtist(artistId: number): Promise<ArtistDetail> {
    return request(`/api/v1/artists/${artistId}/enrich`, {
      method: 'POST',
    })
  },

  enrichArtistWatch(
    artistId: number,
  ): Promise<ArtistEnrichWatchResponse> {
    return request(
      `/api/v1/artists/${artistId}/enrich/watch`,
      { method: 'POST' },
    )
  },

  getArtistEnrichStatus(
    artistId: number,
    taskId: string,
  ): Promise<ArtistEnrichStatusResponse> {
    return request(
      `/api/v1/artists/${artistId}/enrich/status`
        + `?task_id=${encodeURIComponent(taskId)}`,
    )
  },

  async resolveArtistByName(name: string): Promise<{ id: number } | null> {
    try {
      return await request<{ id: number }>(
        `/api/v1/artists/resolve?name=${encodeURIComponent(name)}`,
        { method: 'POST' },
      )
    } catch {
      return null
    }
  },

  // ── Track Info ───────────────────────────────

  getTrackInfo(trackId: number): Promise<TrackInfoResponse> {
    return request(`/api/v1/tracks/${trackId}/info`)
  },

  refreshTrackInfo(trackId: number): Promise<TrackInfoResponse> {
    return request(`/api/v1/tracks/${trackId}/info/refresh`, { method: 'POST' })
  },

  // ── Artist Supplemental ──────────────────────

  getArtistSupplemental(artistId: number): Promise<ArtistSupplementalResponse> {
    return request(`/api/v1/artists/${artistId}/supplemental`)
  },

  refreshArtistSupplemental(artistId: number): Promise<ArtistSupplementalResponse> {
    return request(`/api/v1/artists/${artistId}/supplemental/refresh`, { method: 'POST' })
  },
}
