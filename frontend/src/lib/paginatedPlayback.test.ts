import { describe, expect, it, vi } from 'vitest'

import { playFromPaginatedCollection } from './paginatedPlayback'
import type { Track } from '@/types/api'

function mkTrack(id: number): Track {
  return { id, title: `t${id}` } as Track
}

describe('playFromPaginatedCollection', () => {
  it('uses backend queue when it returns more than the clicked track', async () => {
    const playTrack = vi.fn().mockResolvedValue(undefined)
    const loadedTracks = [
      mkTrack(1),
      mkTrack(2),
      mkTrack(3),
      mkTrack(4),
      mkTrack(5),
    ]
    const loadQueue = vi
      .fn()
      .mockResolvedValue([mkTrack(4), mkTrack(5)])

    await playFromPaginatedCollection({
      track: mkTrack(3),
      loadedTracks,
      playTrack,
      loadQueue,
    })

    expect(playTrack).toHaveBeenCalledTimes(1)
    const [, opts] = playTrack.mock.calls[0]
    expect(opts?.contextTracks?.map((t: Track) => t.id)).toEqual([
      3, 4, 5,
    ])
  })

  it('fallback preserves forward direction of the displayed list', async () => {
    const playTrack = vi.fn().mockResolvedValue(undefined)
    const loadedTracks = [
      mkTrack(1),
      mkTrack(2),
      mkTrack(3),
      mkTrack(4),
      mkTrack(5),
    ]
    const loadQueue = vi.fn().mockResolvedValue([])

    await playFromPaginatedCollection({
      track: mkTrack(3),
      loadedTracks,
      playTrack,
      loadQueue,
    })

    const [, opts] = playTrack.mock.calls[0]
    expect(opts?.contextTracks?.map((t: Track) => t.id)).toEqual([
      3, 4, 5,
    ])
  })

  it('fallback never replays tracks above the clicked one', async () => {
    const playTrack = vi.fn().mockResolvedValue(undefined)
    const loadedTracks = [
      mkTrack(1),
      mkTrack(2),
      mkTrack(3),
      mkTrack(4),
      mkTrack(5),
    ]

    await playFromPaginatedCollection({
      track: mkTrack(3),
      loadedTracks,
      playTrack,
    })

    const [, opts] = playTrack.mock.calls[0]
    expect(opts?.contextTracks?.map((t: Track) => t.id)).toEqual([
      3, 4, 5,
    ])
  })

  it('clicking the last item leaves only the clicked track in context', async () => {
    const playTrack = vi.fn().mockResolvedValue(undefined)
    const loadedTracks = [
      mkTrack(1),
      mkTrack(2),
      mkTrack(3),
    ]
    const loadQueue = vi.fn().mockResolvedValue([])

    await playFromPaginatedCollection({
      track: mkTrack(3),
      loadedTracks,
      playTrack,
      loadQueue,
    })

    const [, opts] = playTrack.mock.calls[0]
    expect(opts?.contextTracks?.map((t: Track) => t.id)).toEqual([3])
  })

  it('uses fallback when loadQueue throws', async () => {
    const playTrack = vi.fn().mockResolvedValue(undefined)
    const loadedTracks = [
      mkTrack(10),
      mkTrack(20),
      mkTrack(30),
      mkTrack(40),
    ]
    const loadQueue = vi.fn().mockRejectedValue(new Error('boom'))

    await playFromPaginatedCollection({
      track: mkTrack(20),
      loadedTracks,
      playTrack,
      loadQueue,
    })

    const [, opts] = playTrack.mock.calls[0]
    expect(opts?.contextTracks?.map((t: Track) => t.id)).toEqual([
      20, 30, 40,
    ])
  })

  it('handles empty loadedTracks gracefully', async () => {
    const playTrack = vi.fn().mockResolvedValue(undefined)

    await playFromPaginatedCollection({
      track: mkTrack(42),
      loadedTracks: [],
      playTrack,
    })

    const [, opts] = playTrack.mock.calls[0]
    expect(opts?.contextTracks?.map((t: Track) => t.id)).toEqual([42])
  })
})
