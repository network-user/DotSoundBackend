import type {
  DailyPlaylistResponse,
  Track,
} from '@/types/api'

export function firstTrackFromDailyPlaylist(
  d: DailyPlaylistResponse,
): Track | null {
  return (
    d.internal_tracks[0]
    ?? d.external_tracks[0]
    ?? d.global_top[0]
    ?? null
  )
}
