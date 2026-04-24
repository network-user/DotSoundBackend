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
  catalog_type: 'ugc' | 'licensed' | 'external_reference'
  access_mode:
    | 'internal_stream'
    | 'third_party_stream'
    | 'official_embed'
    | 'external_link'
  source_platform: string | null
  sc_url: string | null
  sc_uri: string | null
  source_url: string | null
  canonical_source_url: string | null
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

export interface SearchSuggestItem {
  kind: 'track' | 'artist'
  id: number
  title: string | null
  name: string | null
}

export interface SearchSuggestResponse {
  items: SearchSuggestItem[]
}

export interface TrackUploadResponse {
  id: number
  title: string
  artist: string | null
  file_key: string | null
  cover_key: string | null
  duration_seconds: number | null
  source: string
  catalog_type: string
  access_mode: string
  source_platform: string | null
  canonical_source_url: string | null
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
  reason: string
  reason_type: 'other' | 'copyright' | 'neighboring_rights'
  contact_email: string | null
  rightsholder_name: string | null
  proof_url: string | null
}

export interface Complaint {
  id: number
  track_id: number
  reported_by_user_id: number
  reason: string
  reason_type: 'other' | 'copyright' | 'neighboring_rights'
  contact_email: string | null
  rightsholder_name: string | null
  proof_url: string | null
  is_resolved: boolean
  created_at: string
}

export interface ComplaintSubmitResponse {
  complaint: Complaint
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

export interface OnboardingStatus {
  onboarding_completed: boolean
  calibration_completed: boolean
  preferred_genres: string[] | null
  preferred_moods: string[] | null
  import_prompt_acknowledged: boolean
  can_import_from_telegram: boolean
  has_telegram_profile_music: boolean | null
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

export interface WordTime {
  text: string
  start_ms: number
  dur_ms: number
  confidence?: number
}

export interface SyncedLine {
  time_ms: number
  text: string
  confidence?: number
  word_times?: WordTime[] | null
}

export interface LyricsResponse {
  track_id: number
  plain_text: string
  synced_lines: SyncedLine[] | null
  source: string
  source_name?: string | null
  sync_source_name?: string | null
  sync_quality?: string | null
  sync_profile?: string | null
  created_at: string
  updated_at: string
}



export interface LyricsAutoResponse {
  task_id: string
}

export interface LyricsAutoStatusResponse {
  status: string
  stage?: string
  percent?: number | null
  logs?: string[]
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

export interface ChatPeer {
  id: number
  first_name: string
  last_name: string | null
  display_name: string | null
  username: string | null
  avatar_key: string | null
}

export interface ChatListItem {
  conversation: ChatConversation
  member: {
    is_pinned: boolean
    is_muted: boolean
    last_read_message_id: number | null
  }
  last_message_at: string | null
  peer?: ChatPeer
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

export type ArtistEnrichmentStatus =
  | 'pending'
  | 'in_progress'
  | 'done'
  | 'not_found'
  | 'failed'

export interface ArtistEnrichWatchResponse {
  task_id: string
}

export interface ArtistEnrichStatusResponse {
  status: 'pending' | 'done' | 'not_found' | 'error'
  stage: string | null
  logs: string[]
}

export interface DiscographyItem {
  title: string
  year?: number
  type?: string
  url?: string
}

export interface ArtistSourceProfile {
  source_id: string
  source_name: string
  source_page_url?: string | null
  bio?: string | null
  birth_date?: string | null
  birthplace?: string | null
  country?: string | null
  image_url?: string | null
  website_url?: string | null
  discography?: DiscographyItem[] | null
}

export interface ArtistDetail {
  id: number
  name: string
  image_key: string | null
  image_url: string | null
  source: string
  bio: string | null
  birth_date: string | null
  age: number | null
  birthplace: string | null
  country: string | null
  website_url: string | null
  enrichment_status: ArtistEnrichmentStatus
  enriched_at: string | null
  track_count: number
  created_at: string
  discography?: DiscographyItem[] | null
  source_profiles?: ArtistSourceProfile[] | null
  primary_source_id?: string | null
}

// ── Track Info ────────────────────────────────────────────────────────────

export type TrackInfoStatus = 'pending' | 'fetching' | 'done' | 'not_found' | 'failed'

export interface TrackInfoResponse {
  status: TrackInfoStatus
  content: string | null
  fetched_at: string | null
}

// ── Artist Supplemental ───────────────────────────────────────────────────

export interface ArtistSupplementalResponse {
  status: string
  content: string | null
  fetched_at: string | null
}

// ── Import ────────────────────────────────────────────────────────────────

export interface ImportAudioInfo {
  file_id: string
  title: string
  performer: string | null
  duration: number | null
  file_size: number | null
}

export interface ImportExternalTrackInfo {
  title: string
  artist: string | null
  duration_seconds: number | null
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
    tracks?: ImportExternalTrackInfo[]
    kind?: string
    source_url?: string
    error_code?: string
    error_message?: string
    imported?: {
      title: string
      status: string
      track_id?: number
      reason?: string
    }[]
  } | null
  queue_position?: number | null
}
