export const USE_INTERNAL_HLS_PLAYBACK = true

export function shouldUseInternalHlsPlayback(track: {
  access_mode?: string | null
  is_public?: boolean | null
  has_hls?: boolean | null
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
  // Tracks still mid-transcode have no HLS bundle yet — going down
  // the HLS path would 404 on master.m3u8 and force a fallback
  // round-trip to progressive on every play. The backend exposes
  // ``has_hls`` (computed from ``hls_manifest_key``) precisely so
  // the frontend can short-circuit that case.
  if (track.has_hls === false) return false
  // PrefetchManager passes a brief shape that still has the raw
  // manifest key; treat an empty key the same as ``has_hls=false``.
  if (
    'hls_manifest_key' in track &&
    (track.hls_manifest_key === null ||
      track.hls_manifest_key === '')
  ) {
    return false
  }
  return true
}
