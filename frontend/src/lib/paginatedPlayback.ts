import type { Track } from '@/types/api'

type PlayTrackWithContext = (
  track: Track,
  opts?: { contextTracks?: Track[] },
) => Promise<void>

interface PlayFromPaginatedCollectionOptions {
  track: Track
  loadedTracks: readonly Track[] | null | undefined
  playTrack: PlayTrackWithContext
  loadQueue?: (
    track: Track,
    fallbackTracks: readonly Track[],
  ) => Promise<readonly Track[]>
}

function tracksAfterClicked(
  track: Track,
  tracks: readonly Track[],
): Track[] {
  const idx = tracks.findIndex((t) => t.id === track.id)
  if (idx < 0) {
    return tracks.filter((t) => t.id !== track.id)
  }
  return tracks.slice(idx + 1)
}

function withTrackFirst(
  track: Track,
  tracks: readonly Track[],
): Track[] {
  const seen = new Set<number>([track.id])
  const contextTracks = [track]
  for (const candidate of tracks) {
    if (seen.has(candidate.id)) continue
    seen.add(candidate.id)
    contextTracks.push(candidate)
  }
  return contextTracks
}

export async function playFromPaginatedCollection({
  track,
  loadedTracks,
  playTrack,
  loadQueue,
}: PlayFromPaginatedCollectionOptions): Promise<void> {
  const loadedAfter =
    loadedTracks && loadedTracks.length > 0
      ? tracksAfterClicked(track, loadedTracks)
      : []
  const fallbackContext = withTrackFirst(track, loadedAfter)

  if (!loadQueue) {
    await playTrack(track, { contextTracks: fallbackContext })
    return
  }

  try {
    const queueTracks = await loadQueue(track, loadedAfter)
    const contextTracks = withTrackFirst(track, queueTracks)
    await playTrack(track, {
      contextTracks:
        contextTracks.length > 1
          ? contextTracks
          : fallbackContext,
    })
  } catch {
    await playTrack(track, { contextTracks: fallbackContext })
  }
}
