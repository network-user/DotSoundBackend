import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
} from 'vitest'

import {
  consumePrefetchedStream,
  tweenVolume,
  type PrefetchedStreamRecord,
} from './playerAudioHelpers'

describe('consumePrefetchedStream', () => {
  function makeRef(
    entries: Array<[number, PrefetchedStreamRecord]> = [],
  ): { current: Map<number, PrefetchedStreamRecord> } {
    return { current: new Map(entries) }
  }

  it('returns null when the cache is empty', () => {
    const ref = makeRef()
    expect(consumePrefetchedStream(ref, 42)).toBeNull()
  })

  it('returns null when the trackId is not present', () => {
    const ref = makeRef([
      [
        7,
        {
          trackId: 7,
          url: 'https://x/7.m3u8',
          streamType: 'hls',
          expiresAt: null,
          resolvedAt: 0,
        },
      ],
    ])
    expect(consumePrefetchedStream(ref, 999)).toBeNull()
    expect(ref.current.has(7)).toBe(true)
  })

  it('consumes (deletes) the entry on a hit', () => {
    const ref = makeRef([
      [
        7,
        {
          trackId: 7,
          url: 'https://x/7.m3u8',
          streamType: 'hls',
          expiresAt: null,
          resolvedAt: 0,
        },
      ],
    ])
    const r = consumePrefetchedStream(ref, 7)
    expect(r).not.toBeNull()
    expect(r?.url).toBe('https://x/7.m3u8')
    expect(r?.stream_type).toBe('hls')
    expect(r?.track_id).toBe(7)
    expect(ref.current.has(7)).toBe(false)
  })

  it('falls back to a 24h expires_in when expiresAt is null', () => {
    const ref = makeRef([
      [
        7,
        {
          trackId: 7,
          url: 'https://x/7.mp3',
          streamType: 'direct',
          expiresAt: null,
          resolvedAt: 0,
        },
      ],
    ])
    const r = consumePrefetchedStream(ref, 7)
    expect(r?.expires_in).toBe(86_400)
  })

  it('rejects entries that are about to expire (within 5s)', () => {
    const now = 1_000_000
    const ref = makeRef([
      [
        7,
        {
          trackId: 7,
          url: 'https://x/7.mp3',
          streamType: 'direct',
          expiresAt: now + 4_000,
          resolvedAt: now,
        },
      ],
    ])
    const r = consumePrefetchedStream(ref, 7, () => now)
    expect(r).toBeNull()
    expect(ref.current.has(7)).toBe(false)
  })

  it('returns a positive integer expires_in for fresh entries', () => {
    const now = 1_000_000
    const ref = makeRef([
      [
        7,
        {
          trackId: 7,
          url: 'https://x/7.mp3',
          streamType: 'direct',
          expiresAt: now + 30_000,
          resolvedAt: now,
        },
      ],
    ])
    const r = consumePrefetchedStream(ref, 7, () => now)
    expect(r?.expires_in).toBe(30)
  })

  it('clamps expires_in to at least 1 second', () => {
    const now = 1_000_000
    const ref = makeRef([
      [
        7,
        {
          trackId: 7,
          url: 'https://x/7.mp3',
          streamType: 'direct',
          expiresAt: now + 5_400,
          resolvedAt: now,
        },
      ],
    ])
    const r = consumePrefetchedStream(ref, 7, () => now)
    expect(r).not.toBeNull()
    expect(r?.expires_in).toBeGreaterThanOrEqual(1)
  })
})

describe('tweenVolume', () => {
  const originalRaf = globalThis.requestAnimationFrame
  const originalCancelRaf = globalThis.cancelAnimationFrame

  beforeEach(() => {
    let frame = 0
    globalThis.requestAnimationFrame = ((
      cb: FrameRequestCallback,
    ): number => {
      frame += 1
      const id = frame
      setTimeout(() => cb(performance.now()), 0)
      return id
    }) as typeof globalThis.requestAnimationFrame
    globalThis.cancelAnimationFrame = ((
      _id: number,
    ): void => undefined) as typeof globalThis.cancelAnimationFrame
  })

  afterEach(() => {
    globalThis.requestAnimationFrame = originalRaf
    globalThis.cancelAnimationFrame = originalCancelRaf
  })

  function makeFakeAudio(): HTMLAudioElement {
    let volume = 1
    return {
      get volume() {
        return volume
      },
      set volume(v: number) {
        volume = v
      },
    } as unknown as HTMLAudioElement
  }

  it('snaps directly when durationMs <= 0', async () => {
    const a = makeFakeAudio()
    a.volume = 0.7
    await tweenVolume(a, 0.2, 0)
    expect(a.volume).toBeCloseTo(0.2, 5)
  })

  it('clamps target above 1.0 to 1.0', async () => {
    const a = makeFakeAudio()
    a.volume = 0.5
    await tweenVolume(a, 5, 0)
    expect(a.volume).toBe(1)
  })

  it('clamps target below 0 to 0', async () => {
    const a = makeFakeAudio()
    a.volume = 0.5
    await tweenVolume(a, -1, 0)
    expect(a.volume).toBe(0)
  })

  it('reaches the target after the tween completes', async () => {
    const a = makeFakeAudio()
    a.volume = 1
    await tweenVolume(a, 0, 1)
    expect(a.volume).toBeCloseTo(0, 5)
  })

  it('keeps volume monotonic on a fade-out', async () => {
    const a = makeFakeAudio()
    a.volume = 1
    const observed: number[] = []
    const realSet = Object.getOwnPropertyDescriptor(
      Object.getPrototypeOf(a),
      'volume',
    )?.set as ((v: number) => void) | undefined
    let storedVolume = 1
    Object.defineProperty(a, 'volume', {
      configurable: true,
      get() {
        return storedVolume
      },
      set(v: number) {
        storedVolume = v
        observed.push(v)
        if (realSet) realSet.call(a, v)
      },
    })
    await tweenVolume(a, 0, 50)
    for (let i = 1; i < observed.length; i += 1) {
      expect(observed[i]).toBeLessThanOrEqual(observed[i - 1])
    }
    expect(observed[observed.length - 1]).toBeCloseTo(0, 5)
  })

  it('resolves cleanly when audio.volume setter throws', async () => {
    const a = {
      get volume() {
        return 1
      },
      set volume(_v: number) {
        throw new Error('volume locked')
      },
    } as unknown as HTMLAudioElement
    await expect(tweenVolume(a, 0.3, 1)).resolves.toBeUndefined()
  })
})
