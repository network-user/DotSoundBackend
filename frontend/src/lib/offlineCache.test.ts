import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'

vi.mock('@/lib/api', () => ({
  api: {
    getOfflineEligibility: vi.fn(),
  },
}))

import {
  cancelAutoCache,
  DownloadAbortedError,
  ensureProgressiveCachedIdsLoaded,
  getAutoCacheEnabled,
  getAutoCacheOnboardingShown,
  getCacheLimitChoice,
  getCachedIdsSync,
  getEffectiveCacheLimit,
  getProgressiveSwAudioUrl,
  isOfflineCacheSupported,
  isProgressiveSwCachedSync,
  markAutoCacheOnboardingShown,
  prefetchProgressiveBodyForCache,
  queueAutoCache,
  setAutoCacheEnabled,
  setCacheLimitChoice,
  subscribeCacheChanges,
} from './offlineCache'
import { api } from './api'

describe('offlineCache settings (localStorage)', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('auto-cache defaults to enabled', () => {
    expect(getAutoCacheEnabled()).toBe(true)
  })

  it('setAutoCacheEnabled persists and round-trips', () => {
    setAutoCacheEnabled(false)
    expect(getAutoCacheEnabled()).toBe(false)
    setAutoCacheEnabled(true)
    expect(getAutoCacheEnabled()).toBe(true)
  })

  it('cache limit defaults to none and round-trips', () => {
    expect(getCacheLimitChoice()).toBe('none')
    setCacheLimitChoice('5gb')
    expect(getCacheLimitChoice()).toBe('5gb')
  })

  it('cache limit rejects invalid stored values', () => {
    localStorage.setItem(
      'setting-offline-cache-limit',
      'bogus',
    )
    expect(getCacheLimitChoice()).toBe('none')
  })

  it('onboarding flag round-trips', () => {
    expect(getAutoCacheOnboardingShown()).toBe(false)
    markAutoCacheOnboardingShown()
    expect(getAutoCacheOnboardingShown()).toBe(true)
  })
})

describe('queueAutoCache gating', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(api.getOfflineEligibility).mockReset()
  })

  it('does nothing when offline cache unsupported (jsdom)', () => {
    expect(isOfflineCacheSupported()).toBe(false)
    queueAutoCache(42)
    expect(
      api.getOfflineEligibility,
    ).not.toHaveBeenCalled()
  })

  it('does nothing when auto-cache disabled', () => {
    setAutoCacheEnabled(false)
    queueAutoCache(42)
    expect(
      api.getOfflineEligibility,
    ).not.toHaveBeenCalled()
  })
})

describe('cancelAutoCache', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('is a no-op for unknown id', () => {
    expect(() => cancelAutoCache(9999)).not.toThrow()
  })

  it('returns without throwing even if cache unsupported', () => {
    expect(() => cancelAutoCache(1)).not.toThrow()
  })
})

describe('subscribeCacheChanges', () => {
  it('returns unsubscribe function', () => {
    const cb = vi.fn()
    const unsubscribe = subscribeCacheChanges(cb)
    expect(typeof unsubscribe).toBe('function')
    unsubscribe()
  })

  it('cachedIds starts empty in fresh env', () => {
    expect(getCachedIdsSync().size).toBe(0)
  })
})

describe('DownloadAbortedError', () => {
  it('extends Error and carries the right name', () => {
    const err = new DownloadAbortedError()
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('DownloadAbortedError')
  })
})

describe('progressive SW cache helpers', () => {
  beforeEach(() => {
    ;(globalThis as { caches?: unknown }).caches = undefined
  })

  it('isProgressiveSwCachedSync returns false in fresh env', () => {
    expect(isProgressiveSwCachedSync(123)).toBe(false)
  })

  it('ensureProgressiveCachedIdsLoaded is a no-op without Cache API', async () => {
    await expect(
      ensureProgressiveCachedIdsLoaded(),
    ).resolves.toBeUndefined()
  })

  it('getProgressiveSwAudioUrl returns null without Cache API', async () => {
    const url = await getProgressiveSwAudioUrl(123)
    expect(url).toBeNull()
  })

  it('writes 200 OK into Cache API explicitly on prefetch', async () => {
    const cacheStore = new Map<string, Response>()
    const cache = {
      match: vi.fn(async (url: string) => cacheStore.get(url)),
      put: vi.fn(async (url: string, res: Response) => {
        cacheStore.set(url, res)
      }),
      keys: vi.fn(async () => []),
    }
    ;(globalThis as { caches?: unknown }).caches = {
      open: vi.fn(async () => cache),
    }
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(new Uint8Array([1, 2, 3]), {
          status: 200,
          headers: {
            'content-type': 'audio/mpeg',
            'content-length': '3',
          },
        }),
      )
    const ok = await prefetchProgressiveBodyForCache(777)
    expect(ok).toBe(true)
    expect(cache.put).toHaveBeenCalledTimes(1)
    expect(cacheStore.size).toBe(1)
    expect(isProgressiveSwCachedSync(777)).toBe(true)
    fetchSpy.mockRestore()
  })
})

describe('getEffectiveCacheLimit', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns the explicit GB choice when set', async () => {
    setCacheLimitChoice('5gb')
    const limit = await getEffectiveCacheLimit()
    expect(limit).toBe(5 * 1024 * 1024 * 1024)
  })

  it('returns Infinity when no limit and no storage quota', async () => {
    setCacheLimitChoice('none')
    const limit = await getEffectiveCacheLimit()
    expect(limit).toBe(Number.POSITIVE_INFINITY)
  })
})
