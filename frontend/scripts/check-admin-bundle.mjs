#!/usr/bin/env node
// Sanity check for admin chunk placement after `npm run build`.
//
// 1. assets/secure/admin-bundle.js must exist.
// 2. /index.html must NOT reference admin-bundle.js; it should only
//    be loaded dynamically by the admin route.
// 3. No other JS chunk except admin-bundle.js should live under
//    assets/secure/ unless explicitly named `admin-*`.
// 4. Public JS chunks must not statically import assets/secure/*.

import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
} from 'node:fs'
import { basename, join } from 'node:path'

const DIST = join(
  process.cwd(),
  '..',
  'app',
  'static',
  'mini_app',
)
const SECURE = join(DIST, 'assets', 'secure')
const INDEX = join(DIST, 'index.html')
const STATIC_SECURE_IMPORT_RE =
  /\b(?:import|export)\s+(?!\()[^;]*?\bfrom\s*["'](?:\.\.?\/)+secure\/[^"']+["']|\bimport\s*["'](?:\.\.?\/)+secure\/[^"']+["']/g

const errors = []

function walk(dir) {
  const out = []
  let entries = []

  try {
    entries = readdirSync(dir)
  } catch {
    return out
  }

  for (const name of entries) {
    const full = join(dir, name)
    let stat

    try {
      stat = statSync(full)
    } catch {
      continue
    }

    if (stat.isDirectory()) {
      out.push(...walk(full))
    } else if (name.endsWith('.js')) {
      out.push(full)
    }
  }

  return out
}

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
      'index.html references admin-bundle.js; it must only be loaded dynamically',
    )
  }
}

for (const jsFile of walk(join(DIST, 'assets'))) {
  if (jsFile.startsWith(SECURE)) continue

  const body = readFileSync(jsFile, 'utf8')
  const matches = body.match(STATIC_SECURE_IMPORT_RE)
  if (!matches) continue

  errors.push(
    `public js chunk ${basename(jsFile)} statically imports secure assets: ${matches.join(', ')}`,
  )
}

if (errors.length) {
  console.error('[admin-bundle] check failed:')
  for (const message of errors) {
    console.error(`  ${message}`)
  }
  process.exit(1)
}

console.log('[admin-bundle] check passed')
