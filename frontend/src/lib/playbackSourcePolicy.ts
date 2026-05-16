export const USE_INTERNAL_HLS_PLAYBACK = false

export function shouldUseInternalHlsPlayback(track: {
  access_mode?: string | null
  is_public?: boolean | null
}): boolean {
  if (!USE_INTERNAL_HLS_PLAYBACK) return false
  return (
    track.is_public !== false &&
    (track.access_mode == null ||
      track.access_mode === 'internal_stream')
  )
}
