import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'

vi.mock('./storage', () => ({
  getStorageQuota: vi.fn(async () => ({ quota: null, usage: null })),
  persistWarmRecord: vi.fn(async () => undefined),
  persistWarmRecords: vi.fn(async () => undefined),
  listWarmRecords: vi.fn(async () => []),
  dropWarmRecord: vi.fn(async () => undefined),
  clearWarmIndex: vi.fn(async () => undefined),
}))

vi.mock('@/lib/offlineCache', () => ({
  getAutoCacheEnabled: vi.fn(() => false),
  getCachedIdsSync: vi.fn(() => new Set<number>()),
  isCachedSync: vi.fn(() => false),
  queueAutoCache: vi.fn(),
}))

vi.mock('./network', () => ({
  readNetworkSnapshot: () => ({
    effectiveType: '4g',
    saveData: false,
    downlinkMbps: null,
  }),
  subscribeToNetworkChanges: () => () => undefined,
}))

import { PrefetchManager } from './PrefetchManager'
import {
  DEFAULT_PREFETCH_POLICY,
  type PrefetchPolicySnapshot,
} from './types'

const FFMPEG_MASTER = [
  '#EXTM3U',
  '#EXT-X-VERSION:3',
  '#EXT-X-STREAM-INF:BANDWIDTH=128000,CODECS="mp4a.40.2"',
  'hi/playlist.m3u8',
  '#EXT-X-STREAM-INF:BANDWIDTH=64000,CODECS="mp4a.40.2"',
  'lo/playlist.m3u8',
  '',
].join('\n')

const VARIANT_PLAYLIST = [
  '#EXTM3U',
  '#EXT-X-VERSION:3',
  '#EXT-X-TARGETDURATION:10',
  '#EXTINF:10.0,',
  '001.ts',
  '#EXTINF:10.0,',
  '002.ts',
  '#EXTINF:10.0,',
  '003.ts',
  '#EXT-X-ENDLIST',
  '',
].join('\n')

interface FetchCall {
  url: string
  headers: Record<string, string>
}

function _buildFetchSpy(): {
  spy: ReturnType<typeof vi.fn>
  calls: FetchCall[]
} {
  const calls: FetchCall[] = []
  const spy = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const headers: Record<string, string> = {}
    if (init?.headers) {
      const h = new Headers(init.headers)
      h.forEach((v, k) => {
        headers[k] = v
      })
    }
    calls.push({ url, headers })

    if (url.endsWith('/master.m3u8')) {
      return new Response(FFMPEG_MASTER, {
        status: 200,
        headers: {
          'content-type': 'application/vnd.apple.mpegurl',
          'content-length': String(FFMPEG_MASTER.length),
        },
      })
    }
    if (url.endsWith('/playlist.m3u8')) {
      return new Response(VARIANT_PLAYLIST, {
        status: 200,
        headers: {
          'content-type': 'application/vnd.apple.mpegurl',
          'content-length': String(VARIANT_PLAYLIST.length),
        },
      })
    }
    if (/\/\d+\.ts$/.test(url)) {
      return new Response(new Uint8Array(4096), {
        status: 200,
        headers: {
          'content-type': 'video/MP2T',
          'content-length': '4096',
        },
      })
    }
    if (url.includes('/audio')) {
      const len = init?.headers
        ? Number(new Headers(init.headers).get('range')?.split('-')[1] ?? 0) +
          1
        : 0
      return new Response(new Uint8Array(Math.max(1, len)), {
        status: 206,
        headers: { 'content-length': String(len || 1) },
      })
    }
    return new Response(null, { status: 404 })
  })
  return { spy, calls }
}

function _policy(
  overrides: Partial<PrefetchPolicySnapshot> = {},
): PrefetchPolicySnapshot {
  return {
    ...DEFAULT_PREFETCH_POLICY,
    concurrentPrefetchLimit: 2,
    warmSegmentsPerTrack: 2,
    initialBytesPerTrack: 4096,
    maxStorageBytes: 1024 * 1024,
    lookaheadByContext: { ...DEFAULT_PREFETCH_POLICY.lookaheadByContext },
    ...overrides,
  }
}

function _makePolicyFetcher(policy: PrefetchPolicySnapshot) {
  return vi.fn(async () => policy)
}

beforeEach(() => {
  try {
    window.localStorage.removeItem('setting-smart-buffering')
  } catch {
    /* ignore */
  }
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('PrefetchManager', () => {
  it('warms HLS master + variant + first N segments', async () => {
    const { spy, calls } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(_makePolicyFetcher(_policy()))
    await m.start()

    const scheduled = await m.enqueue(
      [{ id: 100, is_public: true }],
      { context: 'home' },
    )
    expect(scheduled).toBe(1)

    await vi.waitFor(() => {
      expect(m.wasWarm(100)).toBe(true)
    })

    const urls = calls.map((c) => c.url)
    expect(urls).toContain('/api/v1/tracks/100/hls/master.m3u8')
    expect(
      urls.some((u) => /\/hls\/(lo|hi)\/playlist\.m3u8$/.test(u)),
    ).toBe(true)
    expect(urls.filter((u) => /\/\d+\.ts$/.test(u))).toHaveLength(2)
  })

  it('picks a known variant from the ffmpeg master without leading slash', async () => {
    const { spy, calls } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(_makePolicyFetcher(_policy()))
    await m.start()
    await m.enqueue([{ id: 200, is_public: true }], {
      context: 'home',
    })
    await vi.waitFor(() => expect(m.wasWarm(200)).toBe(true))

    const variantCalls = calls.filter((c) =>
      /\/hls\/(lo|hi)\/playlist\.m3u8$/.test(c.url),
    )
    expect(variantCalls).toHaveLength(1)
    expect(variantCalls[0]!.url).toContain('/lo/playlist.m3u8')
  })

  it('dedupes identical trackId enqueued from two contexts', async () => {
    const { spy, calls } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(_makePolicyFetcher(_policy()))
    await m.start()

    const a = m.enqueue([{ id: 300, is_public: true }], {
      context: 'home',
    })
    const b = m.enqueue([{ id: 300, is_public: true }], {
      context: 'queue',
    })
    const [scheduledA, scheduledB] = await Promise.all([a, b])
    expect(scheduledA + scheduledB).toBe(1)

    await vi.waitFor(() => expect(m.wasWarm(300)).toBe(true))
    const masterCalls = calls.filter((c) =>
      c.url.endsWith('/tracks/300/hls/master.m3u8'),
    )
    expect(masterCalls).toHaveLength(1)
  })

  it('skips third-party-stream tracks when policy says so', async () => {
    const { spy, calls } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(
      _makePolicyFetcher(
        _policy({ skipThirdPartyAudioCache: true }),
      ),
    )
    await m.start()

    const scheduled = await m.enqueue(
      [
        {
          id: 400,
          is_public: true,
          access_mode: 'third_party_stream',
        },
      ],
      { context: 'home' },
    )
    expect(scheduled).toBe(1)

    await new Promise((r) => setTimeout(r, 30))
    const urls = calls.map((c) => c.url)
    expect(
      urls.some((u) => u.endsWith('/tracks/400/hls/master.m3u8')),
    ).toBe(false)
    expect(urls.some((u) => u.includes('/tracks/400/audio'))).toBe(
      false,
    )
  })

  it('does not server-warm third-party radio tracks', async () => {
    const { spy, calls } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(
      _makePolicyFetcher(
        _policy({ skipThirdPartyAudioCache: true }),
      ),
    )
    await m.start()

    const scheduled = await m.enqueue(
      [
        {
          id: 401,
          is_public: true,
          access_mode: 'third_party_stream',
        },
      ],
      { context: 'radio' },
    )

    expect(scheduled).toBe(0)
    expect(calls.map((c) => c.url)).not.toContain('/api/v1/tracks/prefetch')
    expect(m.wasWarm(401)).toBe(false)
  })

  it('replaceContext: false preserves siblings under the same context', async () => {
    const { spy } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(
      _makePolicyFetcher(
        _policy({
          lookaheadByContext: {
            ...DEFAULT_PREFETCH_POLICY.lookaheadByContext,
            chat_shared: 5,
          },
        }),
      ),
    )
    await m.start()

    await m.enqueue([{ id: 1001, is_public: true }], {
      context: 'chat_shared',
      replaceContext: false,
    })
    await m.enqueue([{ id: 1002, is_public: true }], {
      context: 'chat_shared',
      replaceContext: false,
    })

    await vi.waitFor(() => {
      expect(m.wasWarm(1001) && m.wasWarm(1002)).toBe(true)
    })
  })

  it('counts hits and misses via markPlaybackStart', async () => {
    const { spy } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(_makePolicyFetcher(_policy()))
    await m.start()

    await m.enqueue([{ id: 500, is_public: true }], {
      context: 'home',
    })
    await vi.waitFor(() => expect(m.wasWarm(500)).toBe(true))

    expect(m.markPlaybackStart(500)).toBe(true)
    expect(m.markPlaybackStart(999)).toBe(false)

    const stats = m.status().stats
    expect(stats.hits).toBe(1)
    expect(stats.misses).toBe(1)
    expect(stats.warmed).toBe(1)
  })

  it('refuses new HLS warm-ups once budget is exhausted', async () => {
    const { spy, calls } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(
      _makePolicyFetcher(
        _policy({ maxStorageBytes: 100, warmSegmentsPerTrack: 1 }),
      ),
    )
    await m.start()

    await m.enqueue([{ id: 600, is_public: true }], {
      context: 'home',
    })
    await vi.waitFor(() => expect(m.wasWarm(600)).toBe(true))

    expect(m.status().stats.bytesUsed).toBeGreaterThan(100)

    const before = calls.length
    const scheduled = await m.enqueue(
      [{ id: 601, is_public: true }],
      { context: 'home' },
    )
    expect(scheduled).toBe(0)
    expect(m.status().stats.overBudget).toBeGreaterThanOrEqual(1)
    expect(calls.length).toBe(before)
  })

  it('cancelContext aborts pending warm tasks for that context', async () => {
    const slowSpy = vi.fn(
      (input: RequestInfo, init?: RequestInit) =>
        new Promise<Response>((_, reject) => {
          if (init?.signal) {
            init.signal.addEventListener('abort', () => {
              reject(
                new DOMException('aborted', 'AbortError'),
              )
            })
          }
          void input
        }),
    )
    vi.stubGlobal('fetch', slowSpy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(_makePolicyFetcher(_policy()))
    await m.start()

    void m.enqueue([{ id: 700, is_public: true }], {
      context: 'radio',
    })
    await new Promise((r) => setTimeout(r, 5))
    m.cancelContext('radio')

    await new Promise((r) => setTimeout(r, 20))
    expect(m.wasWarm(700)).toBe(false)
  })

  it('respects user toggle off (smart-buffering disabled)', async () => {
    const { spy, calls } = _buildFetchSpy()
    vi.stubGlobal('fetch', spy)

    const m = new PrefetchManager()
    m.configurePolicyFetcher(_makePolicyFetcher(_policy()))
    await m.start()
    m.setUserEnabled(false)

    const scheduled = await m.enqueue(
      [{ id: 800, is_public: true }],
      { context: 'home' },
    )
    expect(scheduled).toBe(0)
    expect(calls).toHaveLength(0)
  })
})
