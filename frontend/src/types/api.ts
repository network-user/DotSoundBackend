export interface Track {
  id: number
  title: string
  artist: string | null
  genre: string | null
  description: string | null
  duration_seconds: number | null
  cover_key: string | null
  play_count: number
  is_active: boolean
  is_public: boolean
  source: 'internal' | 'soundcloud' | 'telegram'
  sc_url: string | null
  sc_uri: string | null
  source_url: string | null
  source_name: string | null
  uploaded_by_id: number | null
  video_key: string | null
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
  stream_type: 'direct' | 'hls'
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
  page: number
  has_more: boolean
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
  telegram_id: number | null
  username: string | null
  first_name: string | null
  last_name: string | null
  display_name: string | null
  avatar_key: string | null
  email: string | null
  email_verified: boolean
  auth_provider: string
  totp_enabled: boolean
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
  telegram_id: number | null
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

export interface EmailVerifyResponse {
  access_token: string | null
  token_type: string
  user_id: number | null
  is_admin: boolean
  requires_2fa: boolean
  session_token: string | null
}

export interface TwoFASetupResponse {
  otpauth_uri: string
  qr_code_base64: string
  backup_codes: string[]
}

// ── Chat ───────────────────────────────────────────────────────────────────

export interface ChatConversation {
  id: number
  type: 'dm' | 'group' | 'saved'
  title: string | null
  created_by_id: number
  created_at: string
}

export interface ChatListItem {
  conversation: ChatConversation
  member: { is_pinned: boolean; is_muted: boolean; last_read_message_id: number | null }
  last_message_at: string | null
}

export interface MessageAttachment {
  id: number
  file_key: string
  file_type: 'photo' | 'voice'
  file_size_bytes?: number
  duration_seconds?: number
  waveform?: number[]
  width?: number
  height?: number
}

export interface MessageReaction {
  user_id: number
  reaction_type: string
}

export interface ChatMessage {
  id: number
  conversation_id: number
  sender_id: number
  type: 'text' | 'photo' | 'voice' | 'track_share'
  content: string
  reply_to_id: number | null
  shared_track_id: number | null
  created_at: string
  attachments: MessageAttachment[]
  reactions: MessageReaction[]
}

// ── Comments ───────────────────────────────────────────────────────────────

export interface TrackComment {
  id: number
  track_id: number
  user_id: number
  text: string
  is_pinned: boolean
  created_at: string
  likes: number
  dislikes: number
}

// ── Notifications ──────────────────────────────────────────────────────────

export interface AppNotification {
  id: number
  type: string
  title: string
  body: string
  data: Record<string, unknown> | null
  is_read: boolean
  created_at: string
}

// ── Recommendations ───────────────────────────────────────────────────────

export interface HomeSection {
  title: string
  section_type: string
  tracks: Track[]
}

export interface HomePageResponse {
  sections: HomeSection[]
  maturity: string
}

export interface ArtistInfo {
  id: number
  name: string
  image_key: string | null
  source: string
  bio: string | null
  created_at: string
  track_count?: number
}

// ── Import ────────────────────────────────────────────────────────────────

export interface ImportAudioInfo {
  file_id: string
  title: string
  performer: string | null
  duration: number | null
  file_size: number | null
}

export interface ImportJobResponse {
  id: number
  source: string
  status: string
  total_tracks: number
  completed_tracks: number
  failed_tracks: number
  tracks_data: {
    audios?: ImportAudioInfo[]
    imported?: {
      title: string
      status: string
      track_id?: number
      reason?: string
    }[]
  } | null
}
