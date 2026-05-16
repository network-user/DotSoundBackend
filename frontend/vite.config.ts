import { defineConfig, type Connect, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

const MINI_APP_BASE = '/mini_app/'

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
  if (normalized.includes('node_modules/qrcode/')) {
    return 'admin-qrcode'
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

export default defineConfig({
  plugins: [
    redirectRootToMiniApp(),
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
        'sounds/notify-error.wav',
        'sounds/notify-info.wav',
        'sounds/notify-success.wav',
        'sounds/notify-warning.wav',
        'sounds/tap-soft.wav',
      ],
      manifest: {
        name: '.\u0437\u0432\u0443\u043a — музыка',
        short_name: '.\u0437\u0432\u0443\u043a',
        description:
          '.\u0437\u0432\u0443\u043a — музыка без рекламы, плейлисты, офлайн-доступ.',
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
        globPatterns: [
          '**/*.{js,css,html,svg,woff2}',
        ],
        globIgnores: [
          '**/secure/**',
          '**/assets/hls-*.js',
        ],
        runtimeCaching: [
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
                maxEntries: 80,
                maxAgeSeconds: 60 * 60,
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
                maxEntries: 240,
                maxAgeSeconds: 60 * 60 * 24,
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
                maxEntries: 24,
                maxAgeSeconds: 60 * 60 * 24,
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
      polyfill: false,
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
          if (
            normalized.includes('node_modules/react/') ||
            normalized.includes(
              'node_modules/react-dom/',
            ) ||
            normalized.includes(
              'node_modules/@twa-dev/sdk',
            )
          ) {
            return 'vendor'
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

