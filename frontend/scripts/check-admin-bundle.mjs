#!/usr/bin/env node
// Sanity check for admin chunk placement after `npm run build`.
//
// 1. assets/secure/admin-bundle.js must exist.
// 2. /index.html must NOT reference admin-bundle.js — it should
//    only be loaded dynamically by AdminContext via the signed
//    /mini_app/assets/secure/* URL.
// 3. No other JS chunk except admin-bundle.js should live under
//    assets/secure/ unless explicitly named `admin-*`.

import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const DIST = join(
  process.cwd(),
  '..',
  'app',
  'static',
  'mini_app',
)
const SECURE = join(DIST, 'assets', 'secure')
const INDEX = join(DIST, 'index.html')

const errors = []

const adminFile = join(SECURE, 'admin-bundle.js')
if (!existsSync(adminFile)) {
  errors.push(
    `expected ${adminFile} to exist after build`,
  )
}

if (existsSync(SECURE)) {
  for (const entry of readdirSync(SECURE)) {
    if (
      entry.endsWith('.js') &&
      !entry.startsWith('admin-')
    ) {
      errors.push(
        `unexpected js asset under secure/: ${entry}`,
      )
    }
  }
}

if (existsSync(INDEX)) {
  const html = readFileSync(INDEX, 'utf8')
  if (html.includes('admin-bundle.js')) {
    errors.push(
      'index.html references admin-bundle.js — it must only be loaded via the signed URL',
    )
  }
}

if (errors.length) {
  console.error('[admin-bundle] check failed:')
  for (const message of errors) {
    console.error(`  ${message}`)
  }
  process.exit(1)
}
console.log('[admin-bundle] check passed')
