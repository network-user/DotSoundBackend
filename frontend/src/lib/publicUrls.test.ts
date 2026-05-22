import { describe, expect, it } from 'vitest'

import {
  resolvePublicArtistUrl,
  resolvePublicProfileUrl,
} from '@/lib/publicUrls'

describe('resolvePublicProfileUrl', () => {
  it('normalizes domain root profile paths', () => {
    expect(
      resolvePublicProfileUrl(
        'https://dotsound.example/profile/12',
        12,
      ),
    ).toBe('https://dotsound.example/mini_app/profile/12')
  })

  it('keeps mini_app profile paths', () => {
    expect(
      resolvePublicProfileUrl(
        'https://dotsound.example/mini_app/profile/9',
        9,
      ),
    ).toBe('https://dotsound.example/mini_app/profile/9')
  })

  it('falls back to user id when api url is empty', () => {
    const url = resolvePublicProfileUrl('', 5)
    expect(url).toMatch(/\/mini_app\/profile\/5$/)
  })
})

describe('resolvePublicArtistUrl', () => {
  it('normalizes artist paths', () => {
    expect(
      resolvePublicArtistUrl(
        'https://dotsound.example/artist/3',
        3,
      ),
    ).toBe('https://dotsound.example/mini_app/artist/3')
  })
})
