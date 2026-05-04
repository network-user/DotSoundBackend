import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: [
        'icon-192.svg',
        'icon-512.svg',
        'icon-180.png',
        'icon-192.png',
        'icon-512.png',
        'icon-maskable-512.png',
      ],
      manifest: {
        name: '.sound — музыка',
        short_name: '.sound',
        description:
          '.sound — музыка без рекламы, плейлисты, офлайн-доступ.',
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
            src: 'icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
          {
            src: 'icon-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: 'icon-512.svg',
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
        globIgnores: ['**/secure/**'],
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
    modulePreload: {
      polyfill: true,
      resolveDependencies: (_filename, deps) =>
        deps.filter(
          (d) => !d.includes('admin-bundle'),
        ),
    },
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/src/admin/')) {
            return 'admin-bundle'
          }
          if (id.includes('node_modules/hls.js')) {
            return 'hls'
          }
          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/') ||
            id.includes('node_modules/@twa-dev/sdk')
          ) {
            return 'vendor'
          }
          if (
            id.includes('node_modules/@tanstack/') ||
            id.includes('node_modules/recharts/') ||
            id.includes('node_modules/qrcode/') ||
            id.includes(
              'node_modules/@fingerprintjs/',
            )
          ) {
            return 'admin-bundle'
          }
          return undefined
        },
        assetFileNames: (info) => {
          const name = info.name || ''
          if (name.includes('admin-bundle')) {
            return 'assets/secure/[name][extname]'
          }
          return 'assets/[name]-[hash][extname]'
        },
        chunkFileNames: (info) => {
          if (info.name === 'admin-bundle') {
            return 'assets/secure/admin-bundle.js'
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
