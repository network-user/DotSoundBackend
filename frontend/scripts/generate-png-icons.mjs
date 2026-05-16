#!/usr/bin/env node
// Generate PNG icons from the source .звук wordmark SVG.
// Outputs to frontend/public/ so they end up in the build.
//
// Sizes:
//   - icon-v2-180.png          apple-touch-icon (iOS)
//   - icon-v2-192.png          Android home screen (any)
//   - icon-v2-512.png          install prompt / splash
//   - icon-v2-maskable-512.png safe-area maskable variant (Android)
// Legacy icon-* names are generated too as same-brand fallbacks.

import { mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PUBLIC = join(__dirname, '..', 'public')
mkdirSync(PUBLIC, { recursive: true })

function svgFor(size, padding = 0) {
  const usable = size - padding * 2
  const radius = Math.round(size * 0.16)
  const center = Math.round(size / 2)
  const fontSize = Math.round(usable * 0.29)
  const frameWidth = Math.max(2, Math.round(usable * 0.012))
  const frameX = Math.round(padding + usable * 0.12)
  const frameY = Math.round(padding + usable * 0.32)
  const frameW = Math.round(usable * 0.76)
  const frameH = Math.round(usable * 0.36)
  const frameR = Math.round(usable * 0.08)
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${radius}" fill="#000"/>
  <rect x="${frameX}" y="${frameY}" width="${frameW}" height="${frameH}" rx="${frameR}"
    fill="none" stroke="#fff" stroke-width="${frameWidth}" opacity="0.2"/>
  <text x="${center}" y="${padding + usable * 0.525}"
    font-family="Inter, Arial, sans-serif"
    font-weight="800"
    font-size="${fontSize}"
    fill="#fff"
    text-anchor="middle"
    dominant-baseline="middle"
    letter-spacing="0">.звук</text>
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
  { name: 'icon-v2-180.png', size: 180 },
  { name: 'icon-v2-192.png', size: 192 },
  { name: 'icon-v2-512.png', size: 512 },
  {
    name: 'icon-v2-maskable-512.png',
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
