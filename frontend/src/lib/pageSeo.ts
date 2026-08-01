import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { getBrandLabelForLanguage } from '@/lib/brand'

export type PageSeoInput = {
  title?: string | null
  description?: string | null
  path?: string | null
  noIndex?: boolean
}

const DEFAULT_DESCRIPTION =
  '.\u0437\u0432\u0443\u043a - \u043c\u0443\u0437\u044b\u043a\u0430 \u0431\u0435\u0437 \u0440\u0435\u043a\u043b\u0430\u043c\u044b. \u0421\u0442\u0440\u0438\u043c\u044b, \u043f\u043b\u0435\u0439\u043b\u0438\u0441\u0442\u044b, UGC-\u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430, \u043e\u0444\u043b\u0430\u0439\u043d-\u0434\u043e\u0441\u0442\u0443\u043f. Telegram Mini App, 18+.'

export const DEFAULT_ROBOTS =
  'index,follow,max-image-preview:large'
export const NOINDEX_ROBOTS = 'noindex,nofollow'

// Indexable SPA paths only. Everything else gets noindex at runtime.
const INDEXABLE_PATH_PATTERNS: readonly RegExp[] = [
  /^\/$/,
  /^\/search\/?$/,
  /^\/legal\/?$/,
  /^\/legal\/[a-z0-9-]+\/?$/,
  /^\/profile\/\d+\/?$/,
  /^\/artist\/\d+\/?$/,
  /^\/album\/\d+\/?$/,
  /^\/track\/\d+\/?$/,
  /^\/genre\/[^/]+\/?$/,
  /^\/external\/track\/\d+\/?$/,
  /^\/external\/album\/\d+\/?$/,
]

function detectLanguage(): string {
  try {
    const stored = localStorage.getItem('i18nextLng')
    const nav =
      typeof navigator !== 'undefined' ? navigator.language : ''
    return String(stored || nav || 'ru').toLowerCase()
  } catch {
    return 'ru'
  }
}

export function defaultPageTitle(language?: string | null): string {
  const brand = getBrandLabelForLanguage(language ?? detectLanguage())
  return `${brand} - \u043c\u0443\u0437\u044b\u043a\u0430 \u0431\u0435\u0437 \u0440\u0435\u043a\u043b\u0430\u043c\u044b`
}

function ensureMeta(
  selector: string,
  attrs: Record<string, string>,
): HTMLMetaElement {
  let el = document.querySelector(selector) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    for (const [key, value] of Object.entries(attrs)) {
      el.setAttribute(key, value)
    }
    document.head.appendChild(el)
  }
  return el
}

function ensureLink(
  rel: string,
  attrs: Record<string, string> = {},
): HTMLLinkElement {
  let el = document.querySelector(
    `link[rel="${rel}"]`,
  ) as HTMLLinkElement | null
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    for (const [key, value] of Object.entries(attrs)) {
      el.setAttribute(key, value)
    }
    document.head.appendChild(el)
  }
  return el
}

function miniAppBasePath(): string {
  const base = (import.meta.env.BASE_URL || '/mini_app/').replace(
    /\/?$/,
    '',
  )
  return base || '/mini_app'
}

export function resolveCanonicalUrl(path?: string | null): string {
  const origin =
    typeof window !== 'undefined' ? window.location.origin : ''
  const base = miniAppBasePath()
  const raw = (path || '/').trim() || '/'
  const normalized = raw.startsWith('/') ? raw : `/${raw}`
  if (!origin) {
    return `${base}${normalized === '/' ? '/' : normalized}`
  }
  if (normalized === '/') {
    return `${origin}${base}/`
  }
  return `${origin}${base}${normalized}`
}

export function normalizeAppPath(pathname: string): string {
  const base = miniAppBasePath()
  let path = (pathname || '/').split('?')[0] || '/'
  if (base && (path === base || path.startsWith(`${base}/`))) {
    path = path.slice(base.length) || '/'
  }
  if (!path.startsWith('/')) path = `/${path}`
  if (path.length > 1 && path.endsWith('/')) {
    path = path.slice(0, -1)
  }
  return path || '/'
}

export function shouldNoIndexPath(pathname: string): boolean {
  const path = normalizeAppPath(pathname)
  return !INDEXABLE_PATH_PATTERNS.some((re) => re.test(path))
}

/** Legal docs must be readable before auth / during onboarding. */
export function isLegalPath(pathname: string): boolean {
  const path = normalizeAppPath(pathname)
  return path === '/legal' || path.startsWith('/legal/')
}

export function applyRobotsMeta(noIndex: boolean): () => void {
  if (typeof document === 'undefined') {
    return () => undefined
  }
  const robotsEl = ensureMeta('meta[name="robots"]', {
    name: 'robots',
  })
  const prev = robotsEl.getAttribute('content')
  robotsEl.setAttribute(
    'content',
    noIndex ? NOINDEX_ROBOTS : DEFAULT_ROBOTS,
  )
  return () => {
    if (prev !== null) robotsEl.setAttribute('content', prev)
  }
}

export function useRouteRobotsGuard(): void {
  const { pathname } = useLocation()
  const noIndex = shouldNoIndexPath(pathname)

  useEffect(() => {
    return applyRobotsMeta(noIndex)
  }, [noIndex, pathname])
}

export function applyPageSeo(input: PageSeoInput): () => void {
  if (typeof document === 'undefined') {
    return () => undefined
  }

  const prevTitle = document.title
  const descEl = ensureMeta('meta[name="description"]', {
    name: 'description',
  })
  const ogTitleEl = ensureMeta('meta[property="og:title"]', {
    property: 'og:title',
  })
  const ogDescEl = ensureMeta('meta[property="og:description"]', {
    property: 'og:description',
  })
  const ogUrlEl = ensureMeta('meta[property="og:url"]', {
    property: 'og:url',
  })
  const twitterTitleEl = ensureMeta('meta[name="twitter:title"]', {
    name: 'twitter:title',
  })
  const twitterDescEl = ensureMeta(
    'meta[name="twitter:description"]',
    { name: 'twitter:description' },
  )
  const canonicalEl = ensureLink('canonical', {
    'data-seo': 'canonical',
  })

  const prevDesc = descEl.getAttribute('content')
  const prevOgTitle = ogTitleEl.getAttribute('content')
  const prevOgDesc = ogDescEl.getAttribute('content')
  const prevOgUrl = ogUrlEl.getAttribute('content')
  const prevTwTitle = twitterTitleEl.getAttribute('content')
  const prevTwDesc = twitterDescEl.getAttribute('content')
  const prevCanonical = canonicalEl.getAttribute('href')

  const title = (input.title || '').trim() || defaultPageTitle()
  const description =
    (input.description || '').trim() || DEFAULT_DESCRIPTION
  const canonical = resolveCanonicalUrl(input.path)

  document.title = title
  descEl.setAttribute('content', description)
  ogTitleEl.setAttribute('content', title)
  ogDescEl.setAttribute('content', description)
  ogUrlEl.setAttribute('content', canonical)
  twitterTitleEl.setAttribute('content', title)
  twitterDescEl.setAttribute('content', description)
  canonicalEl.setAttribute('href', canonical)

  // robots meta is owned solely by useRouteRobotsGuard to avoid
  // cleanup races with per-view title hooks.
  const clearExplicitRobots =
    input.noIndex === undefined
      ? null
      : applyRobotsMeta(Boolean(input.noIndex))

  return () => {
    document.title = prevTitle
    if (prevDesc !== null) descEl.setAttribute('content', prevDesc)
    if (prevOgTitle !== null) {
      ogTitleEl.setAttribute('content', prevOgTitle)
    }
    if (prevOgDesc !== null) {
      ogDescEl.setAttribute('content', prevOgDesc)
    }
    if (prevOgUrl !== null) {
      ogUrlEl.setAttribute('content', prevOgUrl)
    }
    if (prevTwTitle !== null) {
      twitterTitleEl.setAttribute('content', prevTwTitle)
    }
    if (prevTwDesc !== null) {
      twitterDescEl.setAttribute('content', prevTwDesc)
    }
    if (prevCanonical !== null) {
      canonicalEl.setAttribute('href', prevCanonical)
    }
    clearExplicitRobots?.()
  }
}

export function usePageSeo(input: PageSeoInput): void {
  const title = input.title ?? null
  const description = input.description ?? null
  const path = input.path ?? null
  const noIndex = input.noIndex

  useEffect(() => {
    return applyPageSeo({
      title,
      description,
      path,
      noIndex,
    })
  }, [title, description, path, noIndex])
}
