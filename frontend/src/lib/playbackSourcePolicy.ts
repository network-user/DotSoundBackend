export const USE_INTERNAL_HLS_PLAYBACK = true

export function shouldUseInternalHlsPlayback(track: {
  access_mode?: string | null
  is_public?: boolean | null
  hls_manifest_key?: string | null
}): boolean {
  if (!USE_INTERNAL_HLS_PLAYBACK) return false
  if (track.is_public === false) return false
  if (
    track.access_mode != null &&
    track.access_mode !== 'internal_stream'
  ) {
    return false
  }
  // Tracks still mid-transcode have no manifest_key yet — going down
  // the HLS path would 404 immediately and force a fallback round-trip
  // to progressive on every play. If the field is present in the API
  // payload and empty, prefer progressive directly.
  if (
    'hls_manifest_key' in track &&
    (track.hls_manifest_key === null ||
      track.hls_manifest_key === '')
  ) {
    return false
  }
  return true
}
