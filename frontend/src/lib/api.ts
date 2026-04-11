import { setInternalUserId } from '@/lib/telegram'
import type {
  AuthorProfile,
  AvatarResponse,
  ComplaintCreate,
  ComplaintSubmitResponse,
  DislikeToggleResponse,
  FollowToggleResponse,
  LikeToggleResponse,
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
  TrackListResponse,
  TrackUploadResponse,
  UserLikesResponse,
  UserResponse,
  UserStatsResponse,
} from '@/types/api'

let accessToken: string | null = null

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers)
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  try {
    const res = await fetch(path, { ...opts, headers })
    if (res.status === 401) {
      console.error(`[API] 401 Unauthorized: ${path}. Token present: ${!!accessToken}`)
    }
    if (!res.ok) throw new Error(`${res.status}`)
    if (res.status === 204) return null as T
    return res.json() as Promise<T>
  } catch (err) {
    console.error(`[API] Fetch error for ${path}:`, err)
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

  getMyTracks(userId: number, page = 1, size = 50): Promise<TrackListResponse> {
    return request(`/api/v1/tracks/my?user_id=${userId}&page=${page}&size=${size}`)
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

  getGenres(): Promise<string[]> {
    return request('/api/v1/tracks/genres')
  },

  postPlay(id: number): Promise<void> {
    return request(`/api/v1/tracks/${id}/play`, { method: 'POST' })
  },

  uploadTrack(formData: FormData): Promise<TrackUploadResponse> {
    return request('/api/v1/tracks/upload', { method: 'POST', body: formData })
  },

  updateTrack(trackId: number, data: { is_public?: boolean }, requesterId: number): Promise<Track> {
    return request(`/api/v1/tracks/${trackId}?requester_id=${requesterId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  deleteTrack(trackId: number, requesterId: number): Promise<void> {
    return request(`/api/v1/tracks/${trackId}?requester_id=${requesterId}`, {
      method: 'DELETE',
    })
  },

  searchSoundCloud(q: string, limit = 20): Promise<SCSearchResult[]> {
    return request(`/api/v1/soundcloud/search?q=${encodeURIComponent(q)}&limit=${limit}`)
  },

  importSCTrack(sc_url: string, uploader_id?: number, is_public = true): Promise<Track> {
    return request('/api/v1/soundcloud/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sc_url, uploader_id, is_public }),
    })
  },

  toggleLike(userId: number, trackId: number): Promise<LikeToggleResponse> {
    return request(`/api/v1/likes/${userId}/${trackId}`, { method: 'POST' })
  },

  toggleDislike(userId: number, track_id: number): Promise<DislikeToggleResponse> {
    return request(`/api/v1/dislikes/${userId}/${track_id}`, { method: 'POST' })
  },

  getLikedTracks(userId: number, size = 200): Promise<UserLikesResponse> {
    return request(`/api/v1/likes/${userId}?size=${size}`)
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

  updateProfile(display_name: string): Promise<UserResponse> {
    return request('/api/v1/users/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name }),
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

  // ── Follow ────────────────────────────────────────────────────────────────

  toggleFollow(targetUserId: number): Promise<FollowToggleResponse> {
    return request(`/api/v1/users/${targetUserId}/follow`, { method: 'POST' })
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
    setInternalUserId(res.user_id)
    return res
  },

  async authMock(user_id: number): Promise<TokenResponse> {
    const res = await request<TokenResponse>(`/api/v1/auth/mock/${user_id}`, {
      method: 'POST',
    })
    accessToken = res.access_token
    setInternalUserId(res.user_id)
    return res
  },

  setToken(token: string | null) {
    accessToken = token
  },

  logout() {
    accessToken = null
    setInternalUserId(null)
  },

  getAuthConfig(): Promise<{
    bot_username: string
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
    setInternalUserId(res.user_id)
    return res
  },

  startTelegramImport(): Promise<any> {
    return request('/api/v1/import/telegram', {
      method: 'POST',
    })
  },

  startImportJob(
    jobId: number,
    trackIndices: number[],
  ): Promise<any> {
    return request(`/api/v1/import/${jobId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        track_indices: trackIndices,
      }),
    })
  },

  getImportStatus(jobId: number): Promise<any> {
    return request(`/api/v1/import/${jobId}/status`)
  },

  getActiveImport(): Promise<any> {
    return request('/api/v1/import/active')
  },

  cancelImport(jobId: number): Promise<any> {
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
}
