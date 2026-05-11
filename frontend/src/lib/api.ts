import {
  getInternalUserId,
  setInternalUserId,
  setIsAdmin,
} from '@/lib/telegram'
import { getAdminApiPath } from '@/lib/adminPath'
import type {
  AppNotification,
  ArtistCatalogReleaseDetail,
  ArtistCatalogReleaseListPayload,
  ArtistDetail,
  ArtistItemsResponse,
  ArtistFollowToggleResponse,
  ArtistFollowStatusResponse,
  ArtistListenersResponse,
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
  ProcessingSnapshot,
  LyricsTranslation,
  LyricsResponse,
  Playlist,
  BCSearchResult,
  PlaylistWithTracks,
  SCSearchResult,
  SearchSuggestResponse,
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
  UserDislikesResponse,
  OnboardingStatus,
  UserResponse,
  UserStatsResponse,
  LinkedAccountInfo,
  YTSearchResult,
  ConnectOAuthResponse,
  AccountImportBody,
  AdminManifestResponse,
  ChatPresenceResponse,
  OAuthLinkedProvider,
  FollowListResponse,
  LinkedPlaylistsResponse,
  PlaylistInviteOut,
  AlbumRecord,
  AlbumWithTracksRecord,
  AcceptedResponse,
  AdjacentTracksResponse,
  AuthConfigResponse,
  BlockListResponse,
  ChatActivityResponse,
  ColistenRoomState,
  ConversationRefResponse,
  DailyMixResponse,
  EqSettingsResponse,
  FollowingStatusResponse,
  HomePageResponse,
  LinkStatusResponse,
  LinkTelegramCodeResponse,
  MessageResponse,
  OkResponse,
  PrefetchPolicyResponse,
  ResolveArtistResponse,
  SearchUserItem,
  SimilarTracksResponse,
  SmartSkipResponse,
  StatusResponse,
  OnboardingGenrePreviewResponse,
  OnboardingArtistItem,
  OnboardingBootstrap,
  OnboardingProfileDefaults,
  OnboardingProfileSubmitRequest,
  OnboardingProfileSubmitResponse,
  OnboardingTasteDecision,
  OnboardingTasteSwipeBatchResponse,
  RadioResponse,
  MyComplaintsResponse,
  UserPresenceResponse,
  TrackQueueResponse,
  UnreadCountResponse,
  UserListeningStatsResponse,
  ArtistListPayload,
  FollowedArtistListResponse,
  GenreMixesResponse,
  GenreMixItem,
  OfflineEligibilityResponse,
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

const RETRY_STATUS = new Set([502, 503, 504])
const RETRY_SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

function _sleep(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms))
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
  if (!headers.has('X-DS-Signal')) {
    try {
      const { getClientSignalToken } = await import(
        '@/lib/clientSignals'
      )
      const token = await getClientSignalToken()
      if (token) headers.set('X-DS-Signal', token)
    } catch {
      /* ignore — anti-abuse signal is best-effort */
    }
  }

  const method = (opts.method || 'GET').toUpperCase()
  const canRetry = RETRY_SAFE_METHODS.has(method)

  let attempt = 0
  const maxAttempts = canRetry ? 2 : 1

  while (true) {
    attempt += 1
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
      if (
        canRetry &&
        attempt < maxAttempts &&
        RETRY_STATUS.has(res.status)
      ) {
        await _sleep(250 + Math.floor(Math.random() * 350))
        continue
      }
      if (!res.ok) {
        const message = await readApiErrorMessage(res)
        throw new Error(message)
      }
      if (res.status === 204) return null as T
      return res.json() as Promise<T>
    } catch (err) {
      const isAbort =
        err instanceof DOMException && err.name === 'AbortError'
      const isNetwork =
        !isAbort &&
        err instanceof TypeError &&
        typeof err.message === 'string' &&
        /fetch|network|failed/i.test(err.message)
      if (
        canRetry &&
        attempt < maxAttempts &&
        isNetwork
      ) {
        await _sleep(250 + Math.floor(Math.random() * 350))
        continue
      }
      console.error(
        `[API] Fetch error for ${path}:`,
        err,
      )
      throw err
    }
  }
}

export const api = {
  getTracks(params?: {
    q?: string
    genre?: string
    size?: number
    page?: number
    playable?: boolean
  }): Promise<TrackListResponse> {
    const sp = new URLSearchParams()
    if (params?.q) sp.set('q', params.q)
    if (params?.genre) sp.set('genre', params.genre)
    if (params?.size) sp.set('size', String(params.size))
    if (params?.page) sp.set('page', String(params.page))
    if (params?.playable) sp.set('playable', 'true')
    const query = sp.toString() ? `?${sp}` : ''
    return request(`/api/v1/tracks${query}`)
  },

  searchSuggest(
    q: string,
    limit = 8,
  ): Promise<SearchSuggestResponse> {
    return request(
      `/api/v1/search/suggest?q=${encodeURIComponent(
        q,
      )}&limit=${limit}`,
    )
  },

  getMyTracks(page = 1, size = 50): Promise<TrackListResponse> {
    return request(`/api/v1/tracks/my?page=${page}&size=${size}`)
  },

  getTrackGenres(): Promise<string[]> {
    return request('/api/v1/tracks/genres')
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

  getFollowedArtistsTracks(
    page = 1,
    size = 20,
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
      `/api/v1/users/me/followed-artists/tracks?${params.toString()}`,
    )
  },

  getListenHistory(
    limit: number = 50,
  ): Promise<TrackListResponse> {
    return request(
      `/api/v1/users/me/listen-history?limit=${limit}`,
    )
  },

  getMyListeningStats(
    periodDays: number = 30,
  ): Promise<UserListeningStatsResponse> {
    return request(
      `/api/v1/users/me/listening-stats?period_days=${periodDays}`,
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
  ): Promise<AdjacentTracksResponse> {
    return request(
      `/api/v1/tracks/${trackId}/adjacent`,
    )
  },

  getTrackQueue(
    trackId: number,
    count = 3,
  ): Promise<TrackQueueResponse> {
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

  getTrackEditContext(trackId: number): Promise<{
    track_id: number
    title: string
    artist: string | null
    genre: string | null
    description: string | null
    is_public: boolean
    cover_key: string | null
    has_lyrics: boolean
    is_processing: boolean
    can_edit_artist: boolean
    can_delete: boolean
  }> {
    return request(`/api/v1/tracks/${trackId}/edit-context`)
  },

  updateTrack(
    trackId: number,
    data: {
      is_public?: boolean
      title?: string
      artist?: string | null
      genre?: string | null
      description?: string | null
    },
  ): Promise<Track> {
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

  searchYouTube(q: string, limit = 10): Promise<YTSearchResult[]> {
    return request(`/api/v1/youtube/search?q=${encodeURIComponent(q)}&limit=${limit}`)
  },

  searchBandcamp(q: string, limit = 10): Promise<BCSearchResult[]> {
    return request(`/api/v1/bandcamp/search?q=${encodeURIComponent(q)}&limit=${limit}`)
  },

  importSCTrack(sc_url: string, is_public = true): Promise<Track> {
    return request('/api/v1/soundcloud/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sc_url, is_public }),
    })
  },

  importYouTubeTrack(yt_url: string, is_public = true): Promise<Track> {
    return request('/api/v1/youtube/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yt_url, is_public }),
    })
  },

  importBandcampTrack(bc_url: string, is_public = true): Promise<Track> {
    return request('/api/v1/bandcamp/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bc_url, is_public }),
    })
  },

  toggleLike(userId: number, trackId: number): Promise<LikeToggleResponse> {
    return request(`/api/v1/likes/${userId}/${trackId}`, { method: 'POST' })
  },

  toggleDislike(userId: number, track_id: number): Promise<DislikeToggleResponse> {
    return request(`/api/v1/dislikes/${userId}/${track_id}`, { method: 'POST' })
  },

  getLikedTracks(
    userId: number,
    page = 1,
    size = 20,
    sourceFilter?: string,
  ): Promise<UserLikesResponse> {
    const params = new URLSearchParams({
      page: String(page),
      size: String(size),
    })
    if (sourceFilter && sourceFilter !== 'all') {
      params.set('source', sourceFilter)
    }
    return request(`/api/v1/likes/${userId}?${params}`)
  },

  getDislikedTracks(
    userId: number,
    page = 1,
    size = 20,
    sourceFilter?: string,
    query?: string,
  ): Promise<UserDislikesResponse> {
    const params = new URLSearchParams({
      page: String(page),
      size: String(size),
    })
    if (sourceFilter && sourceFilter !== 'all') {
      params.set('source', sourceFilter)
    }
    if (query && query.trim()) {
      params.set('q', query.trim())
    }
    return request(`/api/v1/dislikes/${userId}?${params}`)
  },

  submitComplaint(body: ComplaintCreate): Promise<ComplaintSubmitResponse> {
    return request('/api/v1/complaints', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  getPlaylists(
    params?: { page?: number; size?: number },
  ): Promise<Playlist[]> {
    const sp = new URLSearchParams()
    if (params?.page != null) {
      sp.set('page', String(params.page))
    }
    if (params?.size != null) {
      sp.set('size', String(params.size))
    }
    const qs = sp.toString() ? `?${sp}` : ''
    return request(`/api/v1/playlists${qs}`)
  },

  getFeaturedPlaylists(
    limit = 10,
  ): Promise<PlaylistWithTracks[]> {
    return request(
      `/api/v1/playlists/featured?limit=${limit}`,
    )
  },

  getDiscover(
    trendingLimit = 10,
    artistLimit = 8,
  ): Promise<
    import('@/types/api').DiscoverResponse
  > {
    return request(
      `/api/v1/recommendations/discover?trending_limit=${trendingLimit}&artist_limit=${artistLimit}`,
    )
  },

  getPlaylist(id: number): Promise<PlaylistWithTracks> {
    return request(`/api/v1/playlists/${id}`)
  },

  createPlaylist(name: string, isPublic = false): Promise<Playlist> {
    return request('/api/v1/playlists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, is_public: isPublic }),
    })
  },

  addTrackToPlaylist(
    playlistId: number,
    trackId: number,
    position?: number | null,
  ): Promise<void> {
    const body: Record<string, unknown> = { track_id: trackId }
    if (position != null) body.position = position
    return request(`/api/v1/playlists/${playlistId}/tracks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  updatePlaylist(
    playlistId: number,
    body: { name?: string; is_public?: boolean },
  ): Promise<Playlist> {
    return request(`/api/v1/playlists/${playlistId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  uploadPlaylistCover(playlistId: number, file: File): Promise<Playlist> {
    const fd = new FormData()
    fd.append('file', file)
    return request(`/api/v1/playlists/${playlistId}/cover`, {
      method: 'POST',
      body: fd,
    })
  },

  removePlaylistCover(playlistId: number): Promise<Playlist> {
    return request(`/api/v1/playlists/${playlistId}/cover`, {
      method: 'DELETE',
    })
  },

  deletePlaylist(playlistId: number): Promise<void> {
    return request(`/api/v1/playlists/${playlistId}`, { method: 'DELETE' })
  },

  removeTrackFromPlaylist(
    playlistId: number,
    trackId: number,
  ): Promise<void> {
    return request(
      `/api/v1/playlists/${playlistId}/tracks/${trackId}`,
      { method: 'DELETE' },
    )
  },

  setPlaylistTrackOrder(
    playlistId: number,
    trackIds: number[],
  ): Promise<void> {
    return request(`/api/v1/playlists/${playlistId}/track-order`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_ids: trackIds }),
    })
  },

  createPlaylistInvite(playlistId: number): Promise<PlaylistInviteOut> {
    return request(`/api/v1/playlists/${playlistId}/invites`, {
      method: 'POST',
    })
  },

  acceptPlaylistInvite(token: string): Promise<Playlist> {
    return request('/api/v1/playlists/invites/accept', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
  },

  getUserProfile(userId: number): Promise<UserResponse> {
    return request(`/api/v1/users/${userId}`)
  },

  async syncSessionUserFlags(): Promise<void> {
    const uid = getInternalUserId()
    if (!uid) return
    try {
      const me = await request<UserResponse>(`/api/v1/users/${uid}`)
      setIsAdmin(Boolean(me.is_admin))
    } catch {
      /* ignore */
    }
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

  uploadAvatar(formData: FormData): Promise<AvatarResponse> {
    return request('/api/v1/users/me/avatar', {
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

  getLyricsTranslations(
    trackId: number,
  ): Promise<LyricsTranslation[]> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/translations`,
    )
  },

  saveLyricsTranslation(
    trackId: number,
    languageCode: string,
    translatedText: string,
  ): Promise<LyricsTranslation> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/translations/${encodeURIComponent(languageCode)}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          translated_text: translatedText,
        }),
      },
    )
  },

  deleteLyricsTranslation(
    trackId: number,
    languageCode: string,
  ): Promise<void> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/translations/${encodeURIComponent(languageCode)}`,
      { method: 'DELETE' },
    )
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
  ): Promise<StatusResponse> {
    return request(
      `/api/v1/tracks/${trackId}/lyrics/auto/cancel?task_id=${taskId}`,
      {
        method: 'POST',
      },
    )
  },

  processingEventsUrl(trackId: number): string {
    return `/api/v1/tracks/${trackId}/processing/events`
  },

  getProcessingStatus(
    trackId: number,
  ): Promise<ProcessingSnapshot> {
    return request(
      `/api/v1/tracks/${trackId}/processing/status`,
    )
  },

  getAdminManifest(locale?: string): Promise<AdminManifestResponse> {
    const qs = locale ? `?locale=${encodeURIComponent(locale)}` : ''
    return request(`${getAdminApiPath('/manifest')}${qs}`)
  },

  // ── Follow ────────────────────────────────────────────────────────────────

  toggleFollow(targetUserId: number): Promise<FollowToggleResponse> {
    return request(`/api/v1/users/${targetUserId}/follow`, { method: 'POST' })
  },

  getFollowStatus(
    targetUserId: number,
  ): Promise<FollowingStatusResponse> {
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

  hasSession(): boolean {
    const t = accessToken || loadStoredToken()
    if (!t) return false
    return !isTokenExpired(t)
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
    const payload = decodeJwtPayload(token)
    if (typeof payload?.is_admin === 'boolean') {
      setIsAdmin(payload.is_admin)
    }
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

  getMyComplaints(): Promise<MyComplaintsResponse> {
    return request('/api/v1/users/me/complaints')
  },

  updateComplaintStatus(
    id: number,
    body: {
      action: 'accept' | 'dismiss' | 'in_progress'
      note?: string
    },
  ): Promise<OkResponse> {
    return request(getAdminApiPath(`/complaints/${id}`), {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
  },

  getAuthConfig(): Promise<AuthConfigResponse> {
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
  ): Promise<MessageResponse> {
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
  ): Promise<StatusResponse> {
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
  ): Promise<StatusResponse> {
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
  ): Promise<StatusResponse> {
    return request('/api/v1/auth/2fa', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code }),
    })
  },

  getLinkStatus(): Promise<LinkStatusResponse> {
    return request(
      '/api/v1/account/link-status',
    )
  },

  requestLinkEmail(
    email: string,
  ): Promise<StatusResponse> {
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
  ): Promise<StatusResponse> {
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

  generateLinkTelegramCode(): Promise<LinkTelegramCodeResponse> {
    return request(
      '/api/v1/account/link/telegram/generate-code',
      { method: 'POST' },
    )
  },

  mergeAccounts(
    sourceAccountToken: string,
  ): Promise<StatusResponse> {
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

  startVkMusicImport(url: string): Promise<ImportJobResponse> {
    return request('/api/v1/import/vk_music', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
  },

  startSoundCloudPlaylistImport(
    url: string,
  ): Promise<ImportJobResponse> {
    return request('/api/v1/import/soundcloud_playlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
  },

  startSpotifyImport(url: string): Promise<ImportJobResponse> {
    return request('/api/v1/import/spotify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
  },

  getLinkedAccounts(): Promise<LinkedAccountInfo[]> {
    return request('/api/v1/linked-accounts')
  },

  startLinkedAccountConnect(
    provider: OAuthLinkedProvider,
  ): Promise<ConnectOAuthResponse> {
    return request(`/api/v1/linked-accounts/${provider}/connect`, {
      method: 'POST',
    })
  },

  startSpotifyAccountImport(
    body: AccountImportBody = {},
  ): Promise<ImportJobResponse> {
    return request('/api/v1/import/spotify_account', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: body.source ?? 'liked',
        playlist_id: body.playlist_id ?? null,
      }),
    })
  },

  startVkAccountImport(
    body: AccountImportBody = {},
  ): Promise<ImportJobResponse> {
    return request('/api/v1/import/vk_account', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: body.source ?? 'liked',
        playlist_id: body.playlist_id ?? null,
      }),
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

  getEqSettings(): Promise<EqSettingsResponse> {
    return request('/api/v1/users/me/eq')
  },

  getPrefetchPolicy(params: {
    effective_type?: string | null
    save_data?: boolean
    downlink?: number | null
    quota_bytes?: number | null
  }): Promise<PrefetchPolicyResponse> {
    const qs = new URLSearchParams()
    if (params.effective_type) {
      qs.set('effective_type', params.effective_type)
    }
    if (params.save_data) qs.set('save_data', 'true')
    if (typeof params.downlink === 'number') {
      qs.set('downlink', String(params.downlink))
    }
    if (
      typeof params.quota_bytes === 'number' &&
      params.quota_bytes > 0
    ) {
      qs.set('quota_bytes', String(params.quota_bytes))
    }
    const query = qs.toString()
    return request(
      `/api/v1/prefetch/policy${query ? `?${query}` : ''}`,
    )
  },

  warmTrackStreamCache(
    trackIds: number[],
  ): Promise<AcceptedResponse> {
    const ids = trackIds.filter(
      (id) =>
        typeof id === 'number' &&
        Number.isFinite(id) &&
        id > 0,
    )
    if (ids.length === 0) {
      return Promise.resolve({ accepted: 0 })
    }
    return request('/api/v1/tracks/prefetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_ids: ids }),
    })
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

  createDM(
    targetUserId: number,
  ): Promise<ConversationRefResponse> {
    return request('/api/v1/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_user_id: targetUserId }),
    })
  },

  createGroup(
    title: string,
    memberIds: number[],
  ): Promise<ConversationRefResponse> {
    return request('/api/v1/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, member_ids: memberIds }),
    })
  },

  listChats(): Promise<ChatListItem[]> {
    return request('/api/v1/chats')
  },

  getChat(convId: number): Promise<ChatListItem> {
    return request(`/api/v1/chats/${convId}`)
  },

  searchUsers(
    q: string,
    limit = 20,
  ): Promise<SearchUserItem[]> {
    return request(`/api/v1/chats/search-users?q=${encodeURIComponent(q)}&limit=${limit}`)
  },

  getSavedChat(): Promise<ConversationRefResponse> {
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
    shared_album_id?: number
    shared_playlist_id?: number
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

  getActivity(convId: number): Promise<ChatActivityResponse> {
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

  addComment(
    trackId: number,
    text: string,
    parentId?: number,
  ): Promise<TrackComment> {
    const body: { text: string; parent_id?: number } = {
      text,
    }
    if (parentId != null) {
      body.parent_id = parentId
    }
    return request(`/api/v1/tracks/${trackId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  getComments(
    trackId: number,
    cursor?: number,
    limit = 20,
    focusCommentId?: number,
  ): Promise<TrackComment[]> {
    const sp = new URLSearchParams()
    if (cursor != null) sp.set('cursor', String(cursor))
    sp.set('limit', String(limit))
    if (focusCommentId != null) {
      sp.set('focus_comment_id', String(focusCommentId))
    }
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

  listBlocks(): Promise<BlockListResponse> {
    return request('/api/v1/blocks')
  },

  // ── Notifications ──────────────────────────────────

  getNotifications(cursor?: number, limit = 20): Promise<AppNotification[]> {
    const sp = new URLSearchParams()
    if (cursor) sp.set('cursor', String(cursor))
    sp.set('limit', String(limit))
    return request(`/api/v1/notifications?${sp}`)
  },

  getUnreadCount(): Promise<UnreadCountResponse> {
    return request('/api/v1/notifications/unread-count')
  },

  markNotificationRead(notificationId: number): Promise<void> {
    return request('/api/v1/notifications/read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notification_id: notificationId }),
    })
  },

  markNotificationUnread(notificationId: number): Promise<void> {
    return request('/api/v1/notifications/unread', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notification_id: notificationId }),
    })
  },

  deleteNotification(notificationId: number): Promise<void> {
    return request(
      `/api/v1/notifications/${notificationId}`,
      { method: 'DELETE' },
    )
  },

  markAllNotificationsRead(): Promise<void> {
    return request('/api/v1/notifications/read-all', { method: 'POST' })
  },

  // ── Presence ───────────────────────────────────────

  getUserPresence(userId: number): Promise<UserPresenceResponse> {
    return request(`/api/v1/users/${userId}/presence`)
  },

  getChatPresence(convId: number): Promise<ChatPresenceResponse> {
    return request(`/api/v1/chats/${convId}/presence`)
  },

  // ── Onboarding ──────────────────────────────────

  getOnboardingStatus(): Promise<OnboardingStatus> {
    return request('/api/v1/onboarding/status')
  },

  acknowledgeOnboardingImport(): Promise<void> {
    return request('/api/v1/onboarding/import-ack', {
      method: 'POST',
    })
  },

  acknowledgeTutorial(): Promise<void> {
    return request('/api/v1/onboarding/tutorial-ack', {
      method: 'POST',
    })
  },

  replayOnboarding(): Promise<void> {
    return request('/api/v1/onboarding/replay', {
      method: 'POST',
    })
  },

  seedOnboardingTracks(
    trackIds: number[],
  ): Promise<import('@/types/api').SeedTracksResponse> {
    return request('/api/v1/onboarding/seed-tracks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_ids: trackIds }),
    })
  },

  debugResetOnboarding(): Promise<void> {
    return request('/api/v1/users/me/debug/reset-onboarding', {
      method: 'POST',
    })
  },

  getOnboardingGenres(): Promise<string[]> {
    return request('/api/v1/onboarding/genres')
  },

  fetchGenrePreviewQueue(
    genre: string,
    limit: number = 10,
  ): Promise<OnboardingGenrePreviewResponse> {
    const q = new URLSearchParams()
    if (limit) q.set('limit', String(limit))
    const qs = q.toString() ? `?${q.toString()}` : ''
    return request(
      `/api/v1/onboarding/genres/${encodeURIComponent(
        genre,
      )}/preview-queue${qs}`,
    )
  },

  trackPreviewSegmentPath(trackId: number): string {
    return `/api/v1/tracks/${trackId}/audio?force_progressive=true`
  },

  getOnboardingArtists(
    genres?: string[],
  ): Promise<OnboardingArtistItem[]> {
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

  completeOnboarding(legalAcceptedVersion?: string): Promise<void> {
    const body = legalAcceptedVersion
      ? JSON.stringify({
          legal_accepted_version: legalAcceptedVersion,
        })
      : undefined
    return request('/api/v1/onboarding/complete', {
      method: 'POST',
      headers: body
        ? { 'Content-Type': 'application/json' }
        : undefined,
      body,
    })
  },

  smartSkipOnboarding(): Promise<SmartSkipResponse> {
    return request('/api/v1/onboarding/smart-skip', {
      method: 'POST',
    })
  },

  getOnboardingBootstrap(): Promise<OnboardingBootstrap> {
    return request('/api/v1/onboarding/bootstrap')
  },

  getOnboardingProfileDefaults(): Promise<OnboardingProfileDefaults> {
    return request('/api/v1/onboarding/profile-defaults')
  },

  submitOnboardingProfile(
    data: OnboardingProfileSubmitRequest,
  ): Promise<OnboardingProfileSubmitResponse> {
    return request('/api/v1/onboarding/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  getTasteSwipeTracks(count = 5): Promise<Track[]> {
    return request(
      `/api/v1/onboarding/taste-swipe?count=${count}`,
    )
  },

  saveTasteSwipeBatch(
    decisions: { track_id: number; decision: OnboardingTasteDecision }[],
  ): Promise<OnboardingTasteSwipeBatchResponse> {
    return request('/api/v1/onboarding/taste-swipe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decisions }),
    })
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

  getHomeRecommendations(): Promise<HomePageResponse> {
    return request('/api/v1/recommendations/home')
  },

  getSimilarTracks(
    trackId: number,
  ): Promise<SimilarTracksResponse> {
    return request(`/api/v1/recommendations/similar/${trackId}`)
  },

  getDailyMix(): Promise<DailyMixResponse> {
    return request('/api/v1/recommendations/daily-mix')
  },

  getDailyPlaylist(): Promise<import('@/types/api').DailyPlaylistResponse> {
    return request('/api/v1/recommendations/daily-playlist')
  },

  getWeeklyPlaylist(): Promise<
    import('@/types/api').WeeklyPlaylistResponse
  > {
    return request('/api/v1/recommendations/weekly-playlist')
  },

  getUserChoicePlaylist(
    limit = 100,
  ): Promise<import('@/types/api').UserChoicePlaylistResponse> {
    return request(
      `/api/v1/recommendations/user-choice?limit=${limit}`,
    )
  },

  getWeeklyTopPlaylist(
    limit = 50,
  ): Promise<import('@/types/api').WeeklyTopPlaylistResponse> {
    return request(
      `/api/v1/recommendations/weekly-top?limit=${limit}`,
    )
  },

  getForgottenTreasuresPlaylist(
    limit = 50,
  ): Promise<
    import('@/types/api').ForgottenTreasuresPlaylistResponse
  > {
    return request(
      `/api/v1/recommendations/forgotten-treasures`
      + `?limit=${limit}`,
    )
  },

  refreshDailyPlaylist(): Promise<void> {
    return request('/api/v1/recommendations/daily-playlist/refresh', { method: 'POST' })
  },


  // ── Artists ─────────────────────────────────────

  getArtists(
    q?: string,
    limit = 20,
  ): Promise<ArtistItemsResponse> {
    const sp = new URLSearchParams()
    if (q) sp.set('q', q)
    sp.set('limit', String(limit))
    return request(`/api/v1/artists?${sp}`)
  },

  getArtist(artistId: number): Promise<ArtistDetail> {
    return request(`/api/v1/artists/${artistId}`)
  },

  getArtistTracks(
    artistId: number,
    page?: number,
    size?: number,
  ): Promise<TrackListResponse> {
    const p = page || 1
    const sp = new URLSearchParams({ page: String(p) })
    if (size != null) {
      sp.set('size', String(size))
    }
    return request(
      `/api/v1/artists/${artistId}/tracks?${sp}`,
    )
  },

  async getAllArtistTracks(artistId: number): Promise<Track[]> {
    const pageSize = 100
    const first = await api.getArtistTracks(
      artistId,
      1,
      pageSize,
    )
    const out = [...first.items]
    const target = Math.min(first.total, 500)
    let page = 2
    while (out.length < target) {
      const res = await api.getArtistTracks(
        artistId,
        page,
        pageSize,
      )
      out.push(...res.items)
      if (res.items.length === 0) {
        break
      }
      page += 1
      if (page > 20) {
        break
      }
    }
    return out
  },

  listArtistCatalogReleases(
    artistId: number,
  ): Promise<ArtistCatalogReleaseListPayload> {
    return request(
      `/api/v1/artists/${artistId}/catalog/releases`,
    )
  },

  getArtistCatalogRelease(
    artistId: number,
    releaseId: number,
  ): Promise<ArtistCatalogReleaseDetail> {
    return request(
      `/api/v1/artists/${artistId}/catalog/releases/${releaseId}`,
    )
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

  async resolveArtistByName(
    name: string,
  ): Promise<ResolveArtistResponse | null> {
    try {
      return await request<ResolveArtistResponse>(
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

  requestAccountDeletion(
    confirmation: string,
  ): Promise<StatusResponse> {
    return request('/api/v1/users/me', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmation }),
    })
  },

  restoreAccountAfterDeletion(): Promise<UserResponse> {
    return request('/api/v1/users/me/restore', { method: 'POST' })
  },

  getDeletionStatus(): Promise<{
    pending: boolean
    deleted_at: string | null
    grace_until: string | null
  }> {
    return request('/api/v1/users/me/deletion-status')
  },

  restoreTrack(trackId: number): Promise<Track> {
    return request(`/api/v1/tracks/${trackId}/restore`, {
      method: 'POST',
    })
  },

  getMyTrash(
    page = 1,
    size = 50,
  ): Promise<TrackListResponse> {
    return request(
      `/api/v1/tracks/me/trash?page=${page}&size=${size}`,
    )
  },

  getOfflineEligibility(
    trackId: number,
  ): Promise<OfflineEligibilityResponse> {
    return request(
      `/api/v1/tracks/${trackId}/offline-eligibility`,
    )
  },

  getMyTop(window: '7d' | '30d' | '90d' | 'all' = '30d'): Promise<{
    window: string
    top_tracks: Array<{
      id: number
      title: string
      artist: string | null
      play_count: number
      cover_key: string | null
    }>
    top_genres: Array<{ genre: string; completed_listens: number }>
  }> {
    return request(`/api/v1/users/me/top?window=${window}`)
  },

  getMyListeningByDay(days = 7): Promise<{
    days: number
    buckets: Array<{ date: string; minutes: number }>
  }> {
    return request(
      `/api/v1/users/me/listening-by-day?days=${days}`,
    )
  },

  getHomeHighlight(): Promise<
    | {
        kind: string
        reason_code: string
        track_id: number
        title: string
        artist: string | null
        cover_key: string | null
        access_mode: string
        catalog_type: string
        generated_at: string
      }
    | null
  > {
    return request('/api/v1/recommendations/home-highlight')
  },

  getFollowingFeed(page = 1, size = 20): Promise<TrackListResponse> {
    return request(`/api/v1/users/me/feed?page=${page}&size=${size}`)
  },

  listFollowers(
    userId: number,
    page = 1,
    size = 20,
  ): Promise<FollowListResponse> {
    return request(
      `/api/v1/users/${userId}/followers?page=${page}&size=${size}`,
    )
  },

  listFollowingUsers(
    userId: number,
    page = 1,
    size = 20,
  ): Promise<FollowListResponse> {
    return request(
      `/api/v1/users/${userId}/following?page=${page}&size=${size}`,
    )
  },

  getPopularPlatformGenres(limit = 50): Promise<string[]> {
    return request(`/api/v1/metadata/genres?limit=${limit}`)
  },

  disconnectLinkedAccount(
    provider: OAuthLinkedProvider,
  ): Promise<void> {
    return request(`/api/v1/linked-accounts/${provider}`, {
      method: 'DELETE',
    })
  },

  getLinkedProviderPlaylists(
    provider: OAuthLinkedProvider,
  ): Promise<LinkedPlaylistsResponse> {
    return request(`/api/v1/linked-accounts/${provider}/playlists`)
  },

  listUserAlbums(
    userId: number,
    page = 1,
    size = 50,
  ): Promise<AlbumRecord[]> {
    return request(
      `/api/v1/users/${userId}/albums?page=${page}&size=${size}`,
    )
  },

  createAlbum(body: {
    title: string
    description?: string | null
    is_public?: boolean
  }): Promise<AlbumRecord> {
    return request('/api/v1/albums', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  getAlbum(albumId: number): Promise<AlbumWithTracksRecord> {
    return request(`/api/v1/albums/${albumId}`)
  },

  updateAlbum(
    albumId: number,
    body: {
      title?: string | null
      description?: string | null
      is_public?: boolean | null
    },
  ): Promise<AlbumRecord> {
    return request(`/api/v1/albums/${albumId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  deleteAlbum(albumId: number): Promise<void> {
    return request(`/api/v1/albums/${albumId}`, { method: 'DELETE' })
  },

  addTrackToAlbum(albumId: number, trackId: number): Promise<void> {
    return request(
      `/api/v1/albums/${albumId}/tracks/${trackId}`,
      { method: 'POST' },
    )
  },

  removeTrackFromAlbum(albumId: number, trackId: number): Promise<void> {
    return request(
      `/api/v1/albums/${albumId}/tracks/${trackId}`,
      { method: 'DELETE' },
    )
  },

  setAlbumTrackOrder(
    albumId: number,
    trackIds: number[],
  ): Promise<void> {
    return request(`/api/v1/albums/${albumId}/track-order`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_ids: trackIds }),
    })
  },

  createColistenRoom(trackId: number): Promise<ColistenRoomState> {
    return request('/api/v1/colisten/rooms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_id: trackId }),
    })
  },

  getColistenRoom(roomId: string): Promise<ColistenRoomState> {
    return request(`/api/v1/colisten/rooms/${roomId}`)
  },

  patchColistenRoom(
    roomId: string,
    body: {
      position_ms?: number | null
      is_playing?: boolean | null
      track_id?: number | null
    },
  ): Promise<ColistenRoomState> {
    return request(`/api/v1/colisten/rooms/${roomId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  addChatMember(convId: number, userId: number): Promise<void> {
    return request(`/api/v1/chats/${convId}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    })
  },

  removeChatMember(convId: number, targetUserId: number): Promise<void> {
    return request(
      `/api/v1/chats/${convId}/members/${targetUserId}`,
      { method: 'DELETE' },
    )
  },

  toggleArtistFollow(
    artistId: number,
  ): Promise<ArtistFollowToggleResponse> {
    return request(`/api/v1/artists/${artistId}/follow`, {
      method: 'POST',
    })
  },

  getArtistFollowStatus(
    artistId: number,
  ): Promise<ArtistFollowStatusResponse> {
    return request(
      `/api/v1/artists/${artistId}/follow/status`,
    )
  },

  getArtistListeners(
    artistId: number,
  ): Promise<ArtistListenersResponse> {
    return request(
      `/api/v1/artists/${artistId}/stats/listeners`,
    )
  },

  listSimilarCatalogArtists(
    artistId: number,
    limit = 10,
  ): Promise<ArtistListPayload> {
    return request(`/api/v1/artists/${artistId}/similar?limit=${limit}`)
  },

  getFollowedArtistsList(
    limit = 50,
  ): Promise<FollowedArtistListResponse> {
    return request(`/api/v1/artists/followed?limit=${limit}`)
  },

  getGenreMixes(): Promise<GenreMixesResponse> {
    return request('/api/v1/recommendations/genre-mixes')
  },

  getGenreMix(
    genre: string,
  ): Promise<GenreMixItem> {
    return request(
      `/api/v1/recommendations/genre-mixes/${encodeURIComponent(genre)}`,
    )
  },

  saveGenreMixOverride(
    genre: string,
    body: {
      title: string
      track_ids: number[]
    },
  ): Promise<GenreMixItem> {
    return request(
      `/api/v1/recommendations/genre-mixes/${encodeURIComponent(genre)}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
  },

  getRadio(
    seedTrackId: number,
    queueSize?: number,
    excludeIds?: number[],
  ): Promise<RadioResponse> {
    const qs = new URLSearchParams()
    qs.set('seed_track_id', String(seedTrackId))
    if (queueSize) qs.set('queue_size', String(queueSize))
    if (excludeIds && excludeIds.length > 0) {
      qs.set('exclude_ids', excludeIds.join(','))
    }
    return request(`/api/v1/recommendations/radio?${qs}`)
  },
}
