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
  const fallbackTracks =
    loadedTracks && loadedTracks.length > 0
      ? withTrackFirst(track, loadedTracks)
      : [track]

  if (!loadQueue) {
    await playTrack(track, { contextTracks: fallbackTracks })
    return
  }

  try {
    const queueTracks = await loadQueue(track, fallbackTracks)
    const contextTracks = withTrackFirst(track, queueTracks)
    await playTrack(track, {
      contextTracks:
        contextTracks.length > 1
          ? contextTracks
          : fallbackTracks,
    })
  } catch {
    await playTrack(track, { contextTracks: fallbackTracks })
  }
}
