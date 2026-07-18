#!/usr/bin/env node
// Open Graph default image (1200x630) in DotBioSite cover style
// (see generate-readme / logo-cover.md and docs/cover.svg).

import { mkdirSync, writeFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PUBLIC = join(__dirname, '..', 'public')
mkdirSync(PUBLIC, { recursive: true })

// OG ratio ~1.91:1. Layout is the DotBioSite skeleton scaled from
// viewBox 1600x900 cover tokens to 1200x630.
const W = 1200
const H = 630

// Equalizer bars glyph (Audio motif from logo-cover.md), 48x48.
const GLYPH =
  '<path d="M8 28 V22 M16 32 V16 M24 35 V13 M32 32 V16 M40 28 V22"/>'

const svg = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="DotSound">
  <title>DotSound</title>
  <defs>
    <linearGradient id="ds-og-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0a0b0d"/>
      <stop offset="0.5" stop-color="#14161a"/>
      <stop offset="1" stop-color="#0b0c0e"/>
    </linearGradient>
    <radialGradient id="ds-og-glow" cx="70%" cy="20%" r="62%">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.14"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.04"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="ds-og-halo" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.1"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#ds-og-bg)"/>
  <rect width="${W}" height="${H}" fill="url(#ds-og-glow)"/>
  <g opacity="0.045" stroke="#ffffff" stroke-width="1">
    <path d="M0 157 H${W} M0 315 H${W} M0 472 H${W} M300 0 V${H} M600 0 V${H} M900 0 V${H}"/>
  </g>
  <circle cx="885" cy="322" r="230" fill="url(#ds-og-halo)"/>
  <svg x="724" y="171" width="300" height="300" viewBox="0 0 48 48">
    <g opacity="0.1" fill="none" stroke="#ffffff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">${GLYPH}</g>
  </svg>
  <svg x="104" y="82" width="64" height="64" viewBox="0 0 48 48">
    <g fill="none" stroke="#f3f3f1" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">${GLYPH}</g>
  </svg>
  <text x="103" y="286" font-family="Inter, Arial, sans-serif" font-size="96" font-weight="800" fill="#f3f3f1" letter-spacing="-2">.звук</text>
  <text x="109" y="338" font-family="Inter, Arial, sans-serif" font-size="28" font-weight="700" fill="#f3f3f1">DotSound</text>
  <text x="109" y="378" font-family="Inter, Arial, sans-serif" font-size="22" fill="#a6a7ab">музыка без рекламы · Telegram Mini App · 18+</text>
</svg>
`.trim()

const svgOut = join(PUBLIC, 'og-default.svg')
const pngOut = join(PUBLIC, 'og-default.png')

writeFileSync(svgOut, `${svg}\n`, 'utf8')
await sharp(Buffer.from(svg))
  .png({ compressionLevel: 9 })
  .toFile(pngOut)

console.log(`[og] wrote ${svgOut}`)
console.log(`[og] wrote ${pngOut}`)
