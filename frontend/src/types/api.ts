export interface TrackPlaybackVariantBrief {
  track_id: number
  source: string
  catalog_type: string
  source_platform: string | null
  source_name: string | null
  is_primary_for_display: boolean
}

export interface TrackArtistBrief {
  id: number
  name: string
  role: string  // "primary" | "featured"
  image_url: string | null
}

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
  source: 'internal' | 'soundcloud' | 'telegram' | 'youtube' | 'bandcamp'
  catalog_type: 'ugc' | 'licensed' | 'external_reference'
  access_mode:
    | 'internal_stream'
    | 'third_party_stream'
    | 'official_embed'
    | 'external_link'
  source_platform: string | null
  imported_from: string | null
  sc_url: string | null
  sc_uri: string | null
  source_url: string | null
  canonical_source_url: string | null
  source_name: string | null
  uploaded_by_id: number | null
  album_id?: number | null
  video_key: string | null
  created_at: string
  waveform_data: number[] | null
  playback_variants?: TrackPlaybackVariantBrief[]
  track_artists?: TrackArtistBrief[]
  resume_position_seconds?: number | null
  last_listen_at?: string | null
  last_listen_seconds?: number | null
  has_lyrics?: boolean
  has_hls?: boolean
}

export interface TrackListResponse {
  items: Track[]
  total: number
  page: number
  size: number
  has_more?: boolean
  next_cursor?: string | null
}

export interface DailyPlaylistResponse {
  internal_tracks: Track[]
  external_tracks: Track[]
  global_top: Track[]
  generated_at: string
  expires_at: string
}

export interface WeeklyPlaylistResponse {
  internal_tracks: Track[]
  external_tracks: Track[]
  generated_at: string
  expires_at: string
}

export interface UserChoicePlaylistResponse {
  tracks: Track[]
  generated_at: string
  score_version: string
}

export interface WeeklyTopPlaylistResponse {
  tracks: Track[]
  generated_at: string
  expires_at: string
  score_version: string
  window_days: number
}

export interface ForgottenTreasuresPlaylistResponse {
  tracks: Track[]
  generated_at: string
  expires_at: string
  score_version: string
  min_like_age_days: number
  silence_days: number
}

export interface SearchSuggestItem {
  kind: 'track' | 'artist'
  id: number
  title: string | null
  name: string | null
  cover_key?: string | null
  duration_seconds?: number | null
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
  playback_variant_track_ids: number[]
}

export interface DislikeToggleResponse {
  track_id: number
  disliked: boolean
  playback_variant_track_ids: number[]
}

export interface LikedTrack extends Track {
  liked_at: string
}

export interface UserLikesResponse {
  items: LikedTrack[]
  total: number
  page: number
  has_more: boolean
}

export interface DislikedTrack extends Track {
  disliked_at: string
}

export interface UserDislikesResponse {
  items: DislikedTrack[]
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

export type PlaylistType =
  | 'user'
  | 'editorial'
  | 'imported_sc'
  | 'imported_bc'
  | 'auto_weekly_top'
  | 'auto_genre_mix'
  | 'auto_daily_mix'

export interface Playlist {
  id: number
  name: string
  is_public: boolean
  owner_id: number
  playlist_type: PlaylistType
  is_featured: boolean
  source_url: string | null
  cover_key: string | null
  cover_auto_suppressed?: boolean
  collage_generated_at?: string | null
  cover_url?: string | null
  description: string | null
  created_at: string
  track_count?: number
}

export interface PlaylistListResponse {
  items: Playlist[]
  total: number
  page: number
  size: number
  has_more: boolean
  next_cursor: string | null
}

export interface PlaylistWithTracks extends Playlist {
  tracks: Track[]
  tracks_total?: number | null
  tracks_page?: number | null
  tracks_size?: number | null
  tracks_has_more?: boolean | null
  tracks_next_cursor?: string | null
}

export interface DiscoverGenreCard {
  genre: string
  title: string
  cover_key: string | null
  track_count: number
}

export interface DiscoverResponse {
  trending_tracks: Track[]
  suggested_artists: ArtistInfo[]
  genre_cards: DiscoverGenreCard[]
  recent_genres: string[]
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
  is_admin?: boolean
  locale?: string | null
  profile_visibility?: 'public' | 'followers_only' | 'hidden'
  profile_access?: 'full' | 'limited'
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

export interface ListeningStatsTopItem {
  name: string
  minutes: number
  plays: number
}

export interface UserListeningStatsResponse {
  period_days: number
  minutes_listened: number
  tracks_listened: number
  top_artists: ListeningStatsTopItem[]
  top_genres: ListeningStatsTopItem[]
}

export interface StatusResponse {
  status: string
}

export interface OkResponse {
  ok: boolean
}

export interface MessageResponse {
  message: string
}

export interface FollowingStatusResponse {
  following: boolean
}

export interface AuthConfigResponse {
  bot_username: string
  debug?: boolean
  admin_panel_path?: string | null
  admin_api_path?: string | null
}

export interface LinkStatusResponse {
  telegram_linked: boolean
  email_linked: boolean
  email: string | null
  telegram_username: string | null
}

export interface LinkTelegramCodeResponse {
  code: string
  bot_username: string
  deep_link: string
}

export interface AdminManifestMenuItem {
  id: string
  label: string
  route: string
  icon?: string
  capability?: string | null
}

export interface AdminManifestSlotAction {
  id: string
  label: string
  capability: string
  icon?: string
  action: string
  confirm?: boolean
}

export interface AdminManifestResponse {
  capabilities: string[]
  menu: AdminManifestMenuItem[]
  slots: Record<string, AdminManifestSlotAction[]>
  adminBundleUrl: string
  issuedAt: number
  expiresIn: number
  locale: string
}

export interface MyComplaintItem {
  id: number
  track_id: number
  reason: string
  reason_type: string
  is_resolved: boolean
  track_hidden?: boolean
  created_at: string
  resolution_note?: string | null
}

export interface MyComplaintsResponse {
  items: MyComplaintItem[]
}

export interface OnboardingStatus {
  onboarding_completed: boolean
  calibration_completed: boolean
  preferred_genres: string[] | null
  preferred_moods: string[] | null
  import_prompt_acknowledged: boolean
  can_import_from_telegram: boolean
  has_telegram_profile_music: boolean | null
  profile_completed: boolean
  legal_accepted_version: string | null
  is_adult_confirmed: boolean
  tutorial_seen: boolean
}

export interface SeedTracksResponse {
  liked: number
  skipped: number
}

export interface OnboardingProfileDefaults {
  suggested_display_name: string
  current_display_name: string | null
  suggested_avatar_url: string | null
  has_custom_avatar: boolean
  auth_provider: string
  suggested_initials: string
  locale: string | null
}

export interface OnboardingProfileSubmitRequest {
  display_name?: string | null
  use_default_avatar?: boolean
  locale?: string | null
}

export interface OnboardingProfileSubmitResponse {
  display_name: string
  avatar_url: string | null
  profile_completed: boolean
}

export interface OnboardingGenreBubble {
  genre: string
  track_count: number
  sample_cover_keys: string[]
}

export interface OnboardingBootstrap {
  status: OnboardingStatus
  profile_defaults: OnboardingProfileDefaults
  genre_bubbles: OnboardingGenreBubble[]
  show_import_offer: boolean
  show_tutorial: boolean
}

export type OnboardingTasteDecision = 'like' | 'dislike' | 'skip'

export interface OnboardingTasteSwipeBatchRequest {
  decisions: { track_id: number; decision: OnboardingTasteDecision }[]
}

export interface OnboardingTasteSwipeBatchResponse {
  saved: number
  swipe_total: number
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

export interface YTSearchResult {
  video_id: string
  title: string
  artist: string | null
  duration_seconds: number | null
  thumbnail_url: string | null
  watch_url: string
}

export interface BCSearchResult {
  result_id: string
  title: string
  artist: string | null
  duration_seconds: number | null
  artwork_url: string | null
  track_url: string
}

export interface AvatarResponse {
  avatar_url: string
}

// ── Track Card ──────────────────────────────────────────────────────────────

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
  album: TrackAlbumInfo | null
  has_lyrics: boolean
  playback_variants?: TrackPlaybackVariantBrief[]
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
  translations?: LyricsTranslation[] | null
  created_at: string
  updated_at: string
}

export interface LyricsTranslation {
  language_code: string
  translated_text: string
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

export type ProcessingStageStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'error'
  | 'skipped'

export interface ProcessingSnapshot {
  track_id: number
  uploaded: ProcessingStageStatus
  cover: ProcessingStageStatus
  audio_analysis: ProcessingStageStatus
  lyrics: ProcessingStageStatus
  overall: 'processing' | 'ready' | 'error'
}

// ── Share ───────────────────────────────────────────────────────────────────

export interface ArtistShareCardResponse {
  artist_id: number
  display_name: string
  image_url: string | null
  profile_url: string
  deep_link: string | null
  total_tracks: number
  followers_count: number
  monthly_listeners: number
  top_track_titles: string[]
}

export interface ShareResponse {
  track_id: number
  url: string
  telegram_share_url: string
}

export interface ShareCardResponse {
  user_id: number
  display_name: string
  username: string | null
  avatar_url: string | null
  profile_url: string
  deep_link: string | null
  total_tracks: number
  total_plays: number
  total_likes: number
  followers_count: number
  top_track_titles: string[]
}

// ── Follow ──────────────────────────────────────────────────────────────────

export interface FollowToggleResponse {
  user_id: number
  following: boolean
}

export interface FollowListUser {
  id: number
  username: string | null
  display_name: string | null
  avatar_key: string | null
}

export interface FollowListResponse {
  items: FollowListUser[]
  total: number
}

export interface AdjacentTracksResponse {
  prev_id: number | null
  next_id: number | null
}

export interface TrackQueueResponse {
  next_tracks: Track[]
}

export interface EqSettingsResponse {
  preset: string | null
  bands: number[]
}

export interface PrefetchPolicyResponse {
  enabled: boolean
  algorithm_version: string
  hot_pool_size: number
  warm_segments_per_track: number
  initial_bytes_per_track: number
  max_storage_bytes: number
  in_memory_ttl_seconds: number
  persistent_ttl_seconds: number
  eviction_policy: string
  concurrent_prefetch_limit: number
  skip_third_party_audio_cache: boolean
  lookahead_by_context: Record<string, number>
  full_download_ahead: number
}

export interface AcceptedResponse {
  accepted: number
}

export interface ConversationRefResponse {
  conversation: { id: number }
}

export interface SearchUserItem {
  id: number
  username: string | null
  first_name: string
  last_name: string | null
  display_name: string | null
  avatar_key: string | null
}

export interface ChatActivityResponse {
  activities: {
    activity: string
    user_id: number
    ts: number
  }[]
}

export interface BlockListResponse {
  blocked_user_ids: number[]
}

export interface UnreadCountResponse {
  count: number
}

export interface UserPresenceResponse {
  user_id: number
  status: string
  last_seen: number
}

export interface ChatPresenceMember {
  status: string
  last_seen: number
}

export interface ChatPresenceResponse {
  conversation_id: number
  members: Record<string, ChatPresenceMember>
}

export interface SimilarTracksResponse {
  seed_track_id: number
  tracks: Track[]
}

export interface DailyMixResponse {
  tracks: Track[]
  generated_at: string
}

export interface ArtistItemsResponse {
  items: ArtistInfo[]
  total: number
}

export interface ResolveArtistResponse {
  id: number
}

export interface OnboardingGenrePreviewResponse {
  items: Track[]
}

export interface OnboardingArtistPreviewResponse {
  items: Track[]
}

export interface OnboardingArtistItem {
  id: number
  name: string
  image_key: string | null
}

export interface SmartSkipResponse {
  applied_genres: string[]
  applied_artist_ids: number[]
  applied_moods: string[]
  enabled: boolean
}

export interface RadioResponse {
  seed_type: string
  seed_id: string
  tracks: Track[]
}

export interface LinkedPlaylistItem {
  id: string
  name: string
  track_count: number | null
  description: string | null
  cover_url: string | null
}

export interface LinkedPlaylistsResponse {
  playlists: LinkedPlaylistItem[]
}

export interface PlaylistInviteOut {
  token: string
  expires_at: string
}

export interface PlaylistCollaboratorItem {
  user_id: number
  role: string
  username: string | null
  display_name: string | null
  created_at: string
}

export interface AlbumRecord {
  id: number
  title: string
  description: string | null
  cover_key: string | null
  owner_id: number
  is_public: boolean
  created_at: string
}

export interface AlbumWithTracksRecord extends AlbumRecord {
  tracks: Track[]
  tracks_total?: number | null
  tracks_page?: number | null
  tracks_size?: number | null
  tracks_has_more?: boolean | null
  tracks_next_cursor?: string | null
}

export interface ColistenRoomState {
  id: string
  host_id: number
  dj_id: number | null
  track_id: number
  position_ms: number
  is_playing: boolean
  epoch: number
  expires_at: string
}

export interface ArtistListPayload {
  items: ArtistInfo[]
  total: number
}

export interface AuthorProfile {
  id: number
  telegram_id: number | null
  username: string | null
  display_name: string | null
  avatar_key: string | null
  is_active: boolean
  created_at: string
  profile_visibility?: 'public' | 'followers_only' | 'hidden'
  profile_access?: 'full' | 'limited'
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
  type:
    | 'text'
    | 'photo'
    | 'voice'
    | 'track_share'
    | 'album_share'
    | 'playlist_share'
  content: string
  reply_to_id: number | null
  shared_track_id: number | null
  shared_album_id: number | null
  shared_playlist_id: number | null
  created_at: string
  attachments: MessageAttachment[]
  reactions: MessageReaction[]
}

// ── Comments ───────────────────────────────────────────────────────────────

export interface TrackComment {
  id: number
  track_id: number
  user_id: number
  parent_id: number | null
  text: string
  is_pinned: boolean
  created_at: string
  likes: number
  dislikes: number
  author_label?: string
  replies?: TrackComment[]
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

export interface HomeHighlight {
  track: Track
  label: string
  reason?: string | null
  hero_image_key?: string | null
}

export interface HomeSection {
  title: string
  section_type: string
  tracks: Track[]
}

export interface HomePageResponse {
  sections: HomeSection[]
  highlights: HomeHighlight[]
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
  monthly_listeners?: number
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
  follower_count?: number
  monthly_listeners?: number
}

export interface ArtistFollowToggleResponse {
  artist_id: number
  following: boolean
  follower_count: number
}

export interface ArtistFollowStatusResponse {
  artist_id: number
  following: boolean
}

export interface MonthlyListenersEntry {
  year: number
  month: number
  unique_listeners: number
  total_plays: number
  total_likes: number
  total_followers: number
}

export interface ArtistListenersResponse {
  artist_id: number
  current_month_listeners: number
  history: MonthlyListenersEntry[]
}

export interface ArtistCatalogReleaseSummary {
  id: number
  title: string
  release_kind: string | null
  released_at: string | null
  display_position: number
  track_count: number
  cover_key: string | null
  cover_url: string | null
}

export interface ArtistCatalogReleaseListPayload {
  items: ArtistCatalogReleaseSummary[]
  total: number
}

export interface ArtistCatalogReleaseTrackRow {
  position: number
  track: Track
}

export interface ArtistCatalogReleaseDetail {
  id: number
  title: string
  release_kind: string | null
  released_at: string | null
  display_position: number
  cover_key: string | null
  cover_url: string | null
  tracks: ArtistCatalogReleaseTrackRow[]
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

export interface ImportDiagnosticEntry {
  provider: string
  stage: string
  method: string
  url: string
  status: number
  elapsed_ms: number
  ok: boolean
  error?: string
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
    scan_dispatched_at?: string
    scan_worker_started?: string
    diagnostics?: ImportDiagnosticEntry[]
    imported?: {
      title: string
      status: string
      track_id?: number
      reason?: string
    }[]
  } | null
  queue_position?: number | null
}

export interface FollowedArtistItem {
  id: number
  name: string
  image_key: string | null
  source: string
  bio: string | null
  track_count: number
}

export interface FollowedArtistListResponse {
  items: FollowedArtistItem[]
  total: number
}

export interface GenreMixItem {
  genre: string
  title: string
  tracks: Track[]
}

export interface GenreMixesResponse {
  mixes: GenreMixItem[]
}

export type OAuthLinkedProvider = 'spotify' | 'soundcloud' | 'vk'

export interface LinkedAccountInfo {
  provider: string
  provider_username: string | null
  provider_user_id: string | null
  connected: boolean
}

export interface ConnectOAuthResponse {
  auth_url: string
}

export interface AccountImportBody {
  source?: 'liked' | 'playlist'
  playlist_id?: string | null
}

/** Stable reason codes returned by the offline-eligibility API.
 *
 * Mirrors ``app/schemas/offline.py::OfflineEligibilityReason``.
 * Keep both ends in sync when adding/removing codes.
 */
export type OfflineEligibilityReason =
  | 'ok'
  | 'third_party_stream'
  | 'official_embed'
  | 'external_reference'
  | 'unknown_mode'
  | 'unknown_access_mode'
  | 'track_too_large'
  | 'policy_unavailable'
  | 'not_found'
  | 'forbidden'

export interface OfflineEligibilityResponse {
  allowed: boolean
  reason: OfflineEligibilityReason | string
  max_track_bytes: number
  max_total_bytes_per_user: number
}

export interface OfflineEligibilityBatchItem {
  allowed: boolean
  reason: OfflineEligibilityReason | string
}

export interface OfflineEligibilityBatchResponse {
  items: Record<string, OfflineEligibilityBatchItem>
  max_track_bytes: number
  max_total_bytes_per_user: number
}

export type PromotionEntityType =
  | 'artist'
  | 'track'
  | 'playlist'
  | 'album'
export type PromotionSurface =
  | 'hero'
  | 'section'
  | 'in_feed'
  | 'search_pin'

export interface PromotionEntityRef {
  entity_type: PromotionEntityType
  entity_id: number
  title: string
  subtitle: string | null
  cover_url: string | null
}

export interface PromotionPublic {
  id: number
  entity_type: PromotionEntityType
  entity_id: number
  surfaces: PromotionSurface[]
  priority: number
  title: string
  subtitle: string | null
  cta_label: string | null
  cover_url: string | null
  entity: PromotionEntityRef
}

export interface PromotionListResponse {
  items: PromotionPublic[]
}
