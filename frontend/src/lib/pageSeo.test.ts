import { afterEach, describe, expect, it } from 'vitest'

import {
  applyPageSeo,
  applyRobotsMeta,
  defaultPageTitle,
  normalizeAppPath,
  resolveCanonicalUrl,
  shouldNoIndexPath,
} from '@/lib/pageSeo'

describe('defaultPageTitle', () => {
  it('uses russian brand for ru', () => {
    expect(defaultPageTitle('ru')).toContain('.\u0437\u0432\u0443\u043a')
  })

  it('uses english brand for en', () => {
    expect(defaultPageTitle('en')).toContain('.sound')
  })
})

describe('resolveCanonicalUrl', () => {
  it('builds mini_app path under current origin', () => {
    const url = resolveCanonicalUrl('/profile/12')
    expect(url).toMatch(/\/mini_app\/profile\/12$/)
  })

  it('normalizes root path', () => {
    const url = resolveCanonicalUrl('/')
    expect(url).toMatch(/\/mini_app\/$/)
  })
})

describe('applyPageSeo', () => {
  afterEach(() => {
    document.title = ''
    document
      .querySelectorAll(
        'meta[name="description"], meta[name="robots"], meta[property="og:title"], meta[property="og:description"], meta[property="og:url"], meta[name="twitter:title"], meta[name="twitter:description"], link[rel="canonical"]',
      )
      .forEach((el) => el.remove())
  })

  it('sets title description and restores previous values', () => {
    document.title = 'prev-title'
    const desc = document.createElement('meta')
    desc.setAttribute('name', 'description')
    desc.setAttribute('content', 'prev-desc')
    document.head.appendChild(desc)

    const restore = applyPageSeo({
      title: 'Artist - .sound',
      description: 'About artist',
      path: '/artist/3',
    })

    expect(document.title).toBe('Artist - .sound')
    expect(
      document
        .querySelector('meta[name="description"]')
        ?.getAttribute('content'),
    ).toBe('About artist')
    expect(
      document
        .querySelector('link[rel="canonical"]')
        ?.getAttribute('href'),
    ).toMatch(/\/mini_app\/artist\/3$/)

    restore()
    expect(document.title).toBe('prev-title')
    expect(
      document
        .querySelector('meta[name="description"]')
        ?.getAttribute('content'),
    ).toBe('prev-desc')
  })

  it('supports explicit noIndex robots override', () => {
    applyPageSeo({
      title: 'Private',
      noIndex: true,
    })
    expect(
      document
        .querySelector('meta[name="robots"]')
        ?.getAttribute('content'),
    ).toBe('noindex,nofollow')
  })
})

describe('shouldNoIndexPath', () => {
  it('allows public shareable and legal paths', () => {
    expect(shouldNoIndexPath('/')).toBe(false)
    expect(shouldNoIndexPath('/search')).toBe(false)
    expect(shouldNoIndexPath('/legal')).toBe(false)
    expect(shouldNoIndexPath('/legal/privacy')).toBe(false)
    expect(shouldNoIndexPath('/profile/12')).toBe(false)
    expect(shouldNoIndexPath('/artist/3')).toBe(false)
    expect(shouldNoIndexPath('/album/9')).toBe(false)
    expect(shouldNoIndexPath('/track/42')).toBe(false)
    expect(shouldNoIndexPath('/genre/rock')).toBe(false)
  })

  it('blocks private app surfaces', () => {
    expect(shouldNoIndexPath('/library')).toBe(true)
    expect(shouldNoIndexPath('/upload')).toBe(true)
    expect(shouldNoIndexPath('/profile')).toBe(true)
    expect(shouldNoIndexPath('/chats')).toBe(true)
    expect(shouldNoIndexPath('/now-playing')).toBe(true)
    expect(shouldNoIndexPath('/recap')).toBe(true)
    expect(shouldNoIndexPath('/admin')).toBe(true)
    expect(shouldNoIndexPath('/settings/connections')).toBe(true)
    expect(shouldNoIndexPath('/artist/3/stats')).toBe(true)
    expect(shouldNoIndexPath('/track/1/edit')).toBe(true)
  })

  it('normalizes mini_app prefix', () => {
    expect(normalizeAppPath('/mini_app/library')).toBe('/library')
    expect(shouldNoIndexPath('/mini_app/profile/7')).toBe(false)
    expect(shouldNoIndexPath('/mini_app/upload')).toBe(true)
  })
})

describe('applyRobotsMeta', () => {
  it('sets and restores robots content', () => {
    const el = document.createElement('meta')
    el.setAttribute('name', 'robots')
    el.setAttribute('content', 'index,follow')
    document.head.appendChild(el)

    const restore = applyRobotsMeta(true)
    expect(el.getAttribute('content')).toBe('noindex,nofollow')
    restore()
    expect(el.getAttribute('content')).toBe('index,follow')
  })
})
