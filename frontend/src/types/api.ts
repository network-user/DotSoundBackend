export interface Track {
  id: number
  title: string
  artist: string | null
  duration_seconds: number | null
  cover_key: string | null
  play_count: number
  is_active: boolean
  is_public: boolean
  source: 'internal' | 'soundcloud' | 'telegram'
  sc_url: string | null
  sc_uri: string | null
  uploaded_by_id: number | null
  created_at: string
}

export interface TrackListResponse {
  items: Track[]
  total: number
  page: number
  size: number
}

export interface TrackUploadResponse {
  id: number
  title: string
  artist: string | null
  file_key: string | null
  cover_key: string | null
  duration_seconds: number | null
  source: string
  is_public: boolean
  created_at: string
}

export interface StreamResponse {
  track_id: number
  url: string
  expires_in: number
}

export interface LikeToggleResponse {
  track_id: number
  liked: boolean
}

export interface DislikeToggleResponse {
  track_id: number
  disliked: boolean
}

export interface UserLikesResponse {
  items: Track[]
  total: number
}

export interface ComplaintCreate {
  track_id: number
  reported_by_user_id: number
  reason: string
  contact_email: string | null
}

export interface ComplaintSubmitResponse {
  complaint: object
  track_hidden: boolean
}

export interface Playlist {
  id: number
  name: string
  is_public: boolean
  owner_id: number
  created_at: string
  track_count?: number
}

export interface PlaylistWithTracks extends Playlist {
  tracks: Track[]
}

export interface UserResponse {
  id: number
  telegram_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  display_name: string | null
  avatar_key: string | null
  is_active: boolean
  created_at: string
}

export interface UserStatsResponse {
  user_id: number
  total_tracks: number
  total_plays: number
  total_likes: number
  followers_count: number
  following_count: number
  top_tracks: Track[]
}

export interface SCSearchResult {
  sc_id: number
  title: string
  artist: string | null
  duration_seconds: number | null
  artwork_url: string | null
  sc_url: string
  sc_uri: string
}

export interface AvatarResponse {
  avatar_url: string
}

// ── Track Card ──────────────────────────────────────────────────────────────

export interface TrackAuthorInfo {
  id: number
  display_name: string | null
  username: string | null
  avatar_key: string | null
}

export interface TrackAlbumInfo {
  id: number
  title: string
  cover_key: string | null
}

export interface TrackCardResponse {
  id: number
  title: string
  artist: string | null
  genre: string | null
  duration_seconds: number | null
  play_count: number
  cover_url: string | null
  created_at: string
  author: TrackAuthorInfo | null
  album: TrackAlbumInfo | null
  has_lyrics: boolean
}

// ── Lyrics ──────────────────────────────────────────────────────────────────

export interface SyncedLine {
  time_ms: number
  text: string
}

export interface LyricsResponse {
  track_id: number
  plain_text: string
  synced_lines: SyncedLine[] | null
  created_at: string
  updated_at: string
}

// ── Share ───────────────────────────────────────────────────────────────────

export interface ShareResponse {
  track_id: number
  url: string
  telegram_share_url: string
}

// ── Follow ──────────────────────────────────────────────────────────────────

export interface FollowToggleResponse {
  user_id: number
  following: boolean
}

export interface AuthorProfile {
  id: number
  telegram_id: number
  username: string | null
  display_name: string | null
  avatar_key: string | null
  is_active: boolean
  created_at: string
}

// ── Auth ────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string
  user_id: number
  is_admin: boolean
}

export interface TelegramAuthRequest {
  init_data: string
}
