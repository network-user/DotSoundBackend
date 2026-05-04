#!/usr/bin/env node
// Generate PNG icons from the source .sound SVG.
// Outputs to frontend/public/ so they end up in the build.
//
// Sizes:
//   - icon-180.png        — apple-touch-icon (iOS)
//   - icon-192.png        — Android home screen (any)
//   - icon-512.png        — install prompt / splash
//   - icon-maskable-512.png — safe-area maskable variant (Android)

import { mkdirSync, writeFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const __dirname = dirname(
  fileURLToPath(import.meta.url),
)
const PUBLIC = join(__dirname, '..', 'public')
mkdirSync(PUBLIC, { recursive: true })

function svgFor(size, padding = 0) {
  const usable = size - padding * 2
  const radius = Math.round(size * 0.16)
  const center = size / 2
  const fontSize = Math.round(usable * 0.24)
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${radius}" fill="#000"/>
  <rect x="${padding + usable * 0.16}" y="${padding + usable * 0.34}" width="${usable * 0.68}" height="${usable * 0.32}" rx="${usable * 0.08}" fill="none" stroke="#fff" stroke-width="${Math.max(2, size * 0.014)}" opacity="0.28"/>
  <text x="${center}" y="${padding + usable * 0.56}"
    font-family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    font-weight="800"
    font-size="${fontSize}"
    fill="#fff"
    text-anchor="middle"
    dominant-baseline="middle"
    letter-spacing="0">.sound</text>
</svg>
`.trim()
}

const targets = [
  { name: 'icon-180.png', size: 180 },
  { name: 'icon-192.png', size: 192 },
  { name: 'icon-512.png', size: 512 },
  {
    name: 'icon-maskable-512.png',
    size: 512,
    padding: 64,
  },
]

for (const t of targets) {
  const svg = svgFor(t.size, t.padding ?? 0)
  const out = join(PUBLIC, t.name)
  await sharp(Buffer.from(svg))
    .png({ compressionLevel: 9 })
    .toFile(out)
  console.log(`[icons] wrote ${out}`)
}

console.log('[icons] done')
