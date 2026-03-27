export interface Track {
  id: number
  title: string
  artist: string | null
  duration_seconds: number | null
  cover_key: string | null
  play_count: number
  is_active: boolean
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
  file_key: string
  cover_key: string | null
  duration_seconds: number | null
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
