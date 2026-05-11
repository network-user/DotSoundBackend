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
  getAutoCacheEnabled,
  getAutoCacheOnboardingShown,
  getCacheLimitChoice,
  getCachedIdsSync,
  isOfflineCacheSupported,
  markAutoCacheOnboardingShown,
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
