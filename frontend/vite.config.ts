import { defineConfig, type Connect, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import fs from 'node:fs'
import path from 'node:path'

const MINI_APP_BASE = '/mini_app/'

const pwaShellGlobPatterns = [
  'index.html',
  'manifest.webmanifest',
  'assets/index-*.js',
  'assets/index-*.css',
  'assets/vendor-*.js',
  'assets/ru-*.js',
  'assets/en-*.js',
]

const normalizeModuleId = (id: string): string =>
  id.replace(/\\/g, '/')

const sanitizeChunkName = (name: string): string =>
  name
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)

const adminDependencyChunk = (id: string): string | null => {
  const normalized = normalizeModuleId(id)
  if (
    normalized.includes(
      'node_modules/@tanstack/react-query',
    ) ||
    normalized.includes(
      'node_modules/@tanstack/query-core',
    )
  ) {
    return 'admin-query'
  }
  if (
    normalized.includes(
      'node_modules/@tanstack/react-table',
    ) ||
    normalized.includes(
      'node_modules/@tanstack/table-core',
    )
  ) {
    return 'admin-table'
  }
  if (
    normalized.includes(
      'node_modules/@fingerprintjs/',
    )
  ) {
    return 'admin-fingerprint'
  }
  if (normalized.includes('node_modules/zustand/')) {
    return 'admin-state'
  }
  return null
}

const publicDependencyChunk = (id: string): string | null => {
  const normalized = normalizeModuleId(id)
  if (
    normalized.includes('node_modules/react/') ||
    normalized.includes('node_modules/react-dom/') ||
    normalized.includes('node_modules/@twa-dev/sdk') ||
    normalized.includes('node_modules/react-router') ||
    normalized.includes('node_modules/i18next') ||
    normalized.includes('node_modules/react-i18next') ||
    normalized.includes('node_modules/framer-motion') ||
    normalized.includes('node_modules/qrcode/')
  ) {
    return 'vendor'
  }
  return null
}

const publicSharedChunk = (id: string): string | null => {
  const normalized = normalizeModuleId(id)
  if (!normalized.includes('/src/')) return null
  if (normalized.includes('/src/admin/')) return null
  if (
    normalized.includes('/src/lib/') ||
    normalized.includes('/src/types/') ||
    normalized.includes('/src/components/ui/') ||
    normalized.includes('/src/components/Icon/') ||
    normalized.includes('/src/components/CoverImage/') ||
    normalized.includes('/src/components/Admin/')
  ) {
    return 'app-shared'
  }
  return null
}

const isAdminSourceModule = (id: string): boolean =>
  normalizeModuleId(id).includes('/src/admin/')

const isAdminBundleChunk = (chunk: {
  moduleIds: readonly string[]
}): boolean =>
  chunk.moduleIds.some(
    (id) =>
      isAdminSourceModule(id) ||
      adminDependencyChunk(id) !== null,
  )

const redirectRootToMiniApp = (): PluginOption => {
  const handler: Connect.NextHandleFunction = (req, res, next) => {
    const rawUrl = req.url || '/'
    const [pathname, search = ''] = rawUrl.split('?')

    if (pathname === '/' || pathname === '/mini_app') {
      const target = MINI_APP_BASE + (search ? '?' + search : '')
      res.statusCode = 302
      res.setHeader('Location', target)
      res.end()
      return
    }

    next()
  }

  return {
    name: 'dotsound:redirect-root-to-mini-app',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(handler)
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler)
    },
  }
}

const siteOrigin = (): string =>
  (
    process.env.VITE_SITE_URL ??
    process.env.VITE_PUBLIC_ORIGIN ??
    ''
  )
    .trim()
    .replace(/\/$/, '')

// Absolute SEO URLs only when origin is known at build time
// (VITE_SITE_URL / VITE_PUBLIC_ORIGIN). Otherwise keep root-relative.
const seoHtmlPlugin = (): PluginOption => {
  const origin = siteOrigin()

  return {
    name: 'dotsound:seo-html',
    transformIndexHtml(html) {
      if (!origin) return html

      const abs = (seoPath: string): string => {
        try {
          return new URL(seoPath, `${origin}/`).toString()
        } catch {
          return seoPath
        }
      }

      let next = html
      const rewrites: Array<[string, string]> = [
        [
          'href="/mini_app/" data-seo="canonical"',
          `href="${abs('/mini_app/')}" data-seo="canonical"`,
        ],
        [
          'content="/mini_app/" data-seo="og-url"',
          `content="${abs('/mini_app/')}" data-seo="og-url"`,
        ],
        [
          'content="/mini_app/og-default.png" data-seo="og-image"',
          `content="${abs('/mini_app/og-default.png')}" data-seo="og-image"`,
        ],
        [
          'content="/mini_app/og-default.png" data-seo="twitter-image"',
          `content="${abs('/mini_app/og-default.png')}" data-seo="twitter-image"`,
        ],
        ['"url": "/mini_app/"', `"url": "${abs('/mini_app/')}"`],
      ]
      for (const [from, to] of rewrites) {
        next = next.replace(from, to)
      }
      return next
    },
  }
}

// Absolute sitemap <loc> + robots Sitemap when origin is known.
// public/ files are copied outside the rollup bundle, so rewrite on disk.
const seoStaticFilesPlugin = (): PluginOption => {
  const origin = siteOrigin()
  let outDir = ''

  return {
    name: 'dotsound:seo-static-files',
    apply: 'build',
    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      if (!origin || !outDir) return

      const sitemapPath = path.join(outDir, 'sitemap.xml')
      if (fs.existsSync(sitemapPath)) {
        const raw = fs.readFileSync(sitemapPath, 'utf8')
        const next = raw.replace(
          /<loc>(\/[^<]*)<\/loc>/g,
          (_m, locPath: string) => {
            try {
              return `<loc>${new URL(locPath, `${origin}/`).toString()}</loc>`
            } catch {
              return `<loc>${locPath}</loc>`
            }
          },
        )
        fs.writeFileSync(sitemapPath, next, 'utf8')
      }

      const robotsPath = path.join(outDir, 'robots.txt')
      if (fs.existsSync(robotsPath)) {
        const raw = fs.readFileSync(robotsPath, 'utf8')
        const next = raw.replace(
          /^Sitemap:\s*\/sitemap\.xml\s*$/m,
          `Sitemap: ${origin}/sitemap.xml`,
        )
        fs.writeFileSync(robotsPath, next, 'utf8')
      }
    },
  }
}

// Self-hosted Umami: инъекция трекера в <head> только на билд-сборке и только
// когда задан VITE_UMAMI_WEBSITE_ID (public client-side id). Скрипт отдаётся
// first-party через /stats/* (см. frontend/nginx.conf), поэтому по умолчанию
// src=/stats/script.js. Если известен origin сайта (VITE_SITE_URL), берём
// абсолютный URL и проставляем data-host-url/data-domains; иначе трекер сам
// возьмёт origin скрипта. Пусто -> плагин ничего не инъектит (dev/CI без ключа).
const umamiPlugin = (): PluginOption => {
  const websiteId = (process.env.VITE_UMAMI_WEBSITE_ID ?? '').trim()
  const rawSrc =
    (process.env.VITE_UMAMI_SRC ?? '').trim() || '/stats/script.js'
  const origin = siteOrigin()

  return {
    name: 'dotsound:umami',
    apply: 'build',
    transformIndexHtml(html) {
      if (!websiteId) return html

      const attrs: Record<string, string | boolean> = {
        defer: true,
        src: rawSrc,
        'data-website-id': websiteId,
      }

      if (origin) {
        try {
          const abs = new URL(rawSrc, origin)
          attrs.src = abs.toString()
          const dir = abs.pathname.replace(/\/[^/]*$/, '')
          attrs['data-host-url'] = (abs.origin + dir).replace(
            /\/$/,
            '',
          )
          attrs['data-domains'] = new URL(origin).host
        } catch {
          // Кривой origin - оставляем относительный src; трекер возьмёт
          // origin самого скрипта (он first-party, так что это корректно).
        }
      }

      return {
        html,
        tags: [{ tag: 'script', attrs, injectTo: 'head' }],
      }
    },
  }
}

export default defineConfig({
  plugins: [
    redirectRootToMiniApp(),
    seoHtmlPlugin(),
    seoStaticFilesPlugin(),
    umamiPlugin(),
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: false,
      includeAssets: [
        'icon-v2-192.svg',
        'icon-v2-512.svg',
        'icon-v2-180.png',
        'icon-v2-192.png',
        'icon-v2-512.png',
        'icon-v2-maskable-512.png',
        'media-session-placeholder-192.png',
        'media-session-placeholder-512.png',
        'media-session-placeholder.svg',
        'sounds/notify-error.wav',
        'sounds/notify-info.wav',
        'sounds/notify-success.wav',
        'sounds/notify-warning.wav',
        'sounds/tap-soft.wav',
      ],
      manifest: {
        name: '.\u0437\u0432\u0443\u043a - \u043c\u0443\u0437\u044b\u043a\u0430',
        short_name: '.\u0437\u0432\u0443\u043a',
        description:
          '.\u0437\u0432\u0443\u043a - \u043c\u0443\u0437\u044b\u043a\u0430 \u0431\u0435\u0437 \u0440\u0435\u043a\u043b\u0430\u043c\u044b. \u0421\u0442\u0440\u0438\u043c\u044b, \u043f\u043b\u0435\u0439\u043b\u0438\u0441\u0442\u044b, UGC, \u043e\u0444\u043b\u0430\u0439\u043d. Telegram Mini App, 18+.',
        lang: 'ru',
        dir: 'ltr',
        categories: ['music', 'entertainment'],
        theme_color: '#000000',
        background_color: '#000000',
        display: 'standalone',
        display_override: ['standalone', 'minimal-ui'],
        orientation: 'portrait',
        id: '/mini_app/',
        start_url: '/mini_app/',
        scope: '/mini_app/',
        prefer_related_applications: false,
        icons: [
          {
            src: 'icon-v2-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'icon-v2-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'icon-v2-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
          {
            src: 'icon-v2-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: 'icon-v2-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any',
          },
        ],
        shortcuts: [
          {
            name: 'Поиск',
            short_name: 'Поиск',
            url: '/mini_app/search',
          },
          {
            name: 'Любимое',
            short_name: 'Любимое',
            url: '/mini_app/library?tab=liked',
          },
          {
            name: 'Загрузить трек',
            short_name: 'Загрузить',
            url: '/mini_app/upload',
          },
        ],
      },
      workbox: {
        globPatterns: pwaShellGlobPatterns,
        globIgnores: [
          '**/secure/**',
          '**/assets/hls-*.js',
        ],
        runtimeCaching: [
          {
            urlPattern:
              /\/mini_app\/assets\/(?!secure\/).+\.(?:js|css)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'mini-app-lazy-assets',
              expiration: {
                maxEntries: 96,
                maxAgeSeconds: 60 * 60 * 24 * 30,
                purgeOnQuotaError: true,
              },
              cacheableResponse: {
                statuses: [200],
              },
            },
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/tracks\/cover_proxy/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'covers-cache',
              expiration: {
                maxEntries: 200,
                maxAgeSeconds: 60 * 60 * 24 * 30,
              },
            },
          },
          {
            urlPattern:
              /\/api\/v1\/tracks\/\d+\/hls\/(?:master|[^/]+\/playlist)\.m3u8/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'hls-manifests-cache',
              expiration: {
                // Manifests are tiny (<2 KB each) and almost never
                // change for a given track once HLS is transcoded
                // (CAS path is content-addressed). Holding 320 of
                // them costs a few hundred KB and lets a long radio
                // / library browsing session re-use them across
                // navigations without round-tripping the backend.
                maxEntries: 320,
                maxAgeSeconds: 60 * 60 * 24,
                purgeOnQuotaError: true,
              },
            },
          },
          {
            urlPattern: /\/api\/v1\/tracks\/\d+\/hls\/[^/]+\/\d+\.ts/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'hls-segments-cache',
              expiration: {
                // With 4s segments a typical 3-min track has ~45
                // segments. 1500 entries comfortably covers a
                // ~30-track radio session, and the segment URLs are
                // immutable (CAS path embeds the source SHA-256) so
                // a 30-day TTL is safe. ``purgeOnQuotaError`` keeps
                // the cache from blocking writes on tight devices.
                maxEntries: 1500,
                maxAgeSeconds: 60 * 60 * 24 * 30,
                purgeOnQuotaError: true,
              },
              rangeRequests: true,
              cacheableResponse: {
                statuses: [200],
              },
              plugins: [
                {
                  cacheWillUpdate: async ({ response }) => {
                    if (response.status === 206) {
                      return null
                    }
                    if (
                      response.headers.get(
                        'X-Offline-Allowed',
                      ) === '0'
                    ) {
                      return null
                    }
                    return response
                  },
                },
              ],
            },
          },
          {
            urlPattern: /\/api\/v1\/tracks\/\d+\/audio(?:\?.*)?$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'progressive-audio-cache',
              expiration: {
                // Bumped from 24 to 48 so a longer radio session
                // can keep its just-played and upcoming progressive
                // tracks warm. 7-day TTL matches the unpinned
                // offline TTL knob in offlineCache.ts.
                maxEntries: 48,
                maxAgeSeconds: 60 * 60 * 24 * 7,
                purgeOnQuotaError: true,
              },
              rangeRequests: true,
              cacheableResponse: {
                statuses: [200],
              },
              plugins: [
                {
                  cacheWillUpdate: async ({ response }) => {
                    if (response.status === 206) {
                      return null
                    }
                    if (
                      response.headers.get(
                        'X-Offline-Allowed',
                      ) === '0'
                    ) {
                      return null
                    }
                    return response
                  },
                },
              ],
            },
          },
          {
            urlPattern:
              /\/api\/v1\/users\/\d+\/(?:likes|history|preferences|me)/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'user-shell-cache',
              expiration: {
                maxEntries: 40,
                maxAgeSeconds: 60 * 60 * 24 * 7,
              },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            // Radio: SWR with a short TTL so the player can lay
            // hands on a queue refill even when the OS has frozen
            // network in the background. The exact-URL match means
            // we only get a cache hit when the same (seed, exclude
            // set) is asked for twice -- usually fine because the
            // pro-active refill in PlayerContext fires the same
            // request once before the queue empties (warm-up) and
            // once when it actually empties (consume the warmed
            // entry). 100 entries is enough to cover 1-2 weeks of
            // listening across multiple seeds; 5-minute TTL is
            // short enough that the user does not get yesterday's
            // recommendations on a fresh tap.
            urlPattern:
              /\/api\/v1\/recommendations\/radio(?:\?.*)?$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'radio-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 300,
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            // The track-queue endpoint is the fallback path for
            // ``preloadFirst`` when ``getRadio`` returns nothing.
            // Caching it with the same SWR strategy means the next
            // track switch after a flaky network gets resolved
            // immediately from cache instead of stalling.
            urlPattern:
              /\/api\/v1\/tracks\/\d+\/queue(?:\?.*)?$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'track-queue-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 300,
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: /\/api\/v1\/users\/me(?:\?.*)?$/,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /^https?:\/\/.*\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 300,
              },
            },
          },
        ],
        navigateFallback: '/mini_app/index.html',
        navigateFallbackAllowlist: [/^\/mini_app/],
        navigateFallbackDenylist: [/^\/admin/, /^\/mini_app\/admin/],
      },
    }),
  ],

  base: '/mini_app/',

  build: {
    outDir: '../app/static/mini_app',
    emptyOutDir: true,
    sourcemap: false,
    modulePreload: {
      polyfill: true,
      resolveDependencies: (_filename, deps) =>
        deps.filter((d) => {
          const normalized = normalizeModuleId(d)
          return (
            !normalized.includes('/secure/') &&
            !normalized.includes('admin-bundle') &&
            !normalized.includes('/hls-')
          )
        }),
    },
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = normalizeModuleId(id)
          const adminDepChunk = adminDependencyChunk(
            normalized,
          )
          if (adminDepChunk) {
            return adminDepChunk
          }
          const publicDepChunk =
            publicDependencyChunk(normalized)
          if (publicDepChunk) {
            return publicDepChunk
          }
          const publicShared =
            publicSharedChunk(normalized)
          if (publicShared) {
            return publicShared
          }
          if (
            normalized.includes(
              '/src/admin/AdminApp.tsx',
            )
          ) {
            return 'admin-bundle'
          }
          if (
            normalized.includes('/src/admin/routes/')
          ) {
            const parsed = path.parse(normalized)
            return `admin-route-${sanitizeChunkName(
              parsed.name,
            )}`
          }
          if (normalized.includes('node_modules/hls.js')) {
            return 'hls'
          }
          return undefined
        },
        assetFileNames: (info) => {
          const name = info.name || ''
          if (name.toLowerCase().includes('admin')) {
            return 'assets/secure/[name][extname]'
          }
          return 'assets/[name]-[hash][extname]'
        },
        chunkFileNames: (info) => {
          if (info.name === 'admin-bundle') {
            return 'assets/secure/admin-bundle.js'
          }
          if (isAdminBundleChunk(info)) {
            const name = info.name.startsWith('admin-')
              ? info.name
              : `admin-${info.name}`
            return `assets/secure/${sanitizeChunkName(
              name,
            )}-[hash].js`
          }
          return 'assets/[name]-[hash].js'
        },
      },
    },
  },

  server: {
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})

