import type {
  Track,
  TrackListResponse,
  TrackUploadResponse,
  StreamResponse,
  LikeToggleResponse,
  UserLikesResponse,
  ComplaintCreate,
  ComplaintSubmitResponse,
  Playlist,
  PlaylistWithTracks,
  UserResponse,
  UserStatsResponse,
} from '@/types/api'

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, opts)
  if (!res.ok) throw new Error(`${res.status}`)
  if (res.status === 204) return null as T
  return res.json() as Promise<T>
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

  getTrack(id: number): Promise<Track> {
    return request(`/api/v1/tracks/${id}`)
  },

  getStream(id: number): Promise<StreamResponse> {
    return request(`/api/v1/tracks/${id}/stream`)
  },

  postPlay(id: number): Promise<void> {
    return request(`/api/v1/tracks/${id}/play`, { method: 'POST' })
  },

  uploadTrack(formData: FormData): Promise<TrackUploadResponse> {
    return request('/api/v1/tracks/upload', { method: 'POST', body: formData })
  },

  toggleLike(userId: number, trackId: number): Promise<LikeToggleResponse> {
    return request(`/api/v1/likes/${userId}/${trackId}`, { method: 'POST' })
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
}
