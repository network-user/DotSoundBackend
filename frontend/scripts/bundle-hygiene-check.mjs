#!/usr/bin/env node
// Fail the build if admin-specific strings leak into the public
// bundle. We scan every file that ships to unauthenticated users
// for a hand-curated blocklist; admin-only chunks live under
// assets/secure/ and are skipped on purpose.

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { basename, join } from 'node:path'

const DIST = join(process.cwd(), '..', 'app', 'static', 'mini_app')
const SKIP_DIR = 'secure'

const BLOCKLIST = [
  'users.grant_admin',
  'tracks.manage',
  'tracks.delete',
  'complaints.moderate',
  'audio_compute.manage',
  'audio_compute.view_audit',
  'audio_compute.rotate_secret',
  'lyrics.routing',
  'settings.manage',
  'feature_flags.manage',
  'security.release_lockout',
  'admin_actions_log',
  'admin_login_attempts',
  'worker_audit_log',
  'admin_totp_secret_encrypted',
]

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
    let s
    try {
      s = statSync(full)
    } catch {
      continue
    }
    if (s.isDirectory()) {
      if (basename(full) === SKIP_DIR) continue
      out.push(...walk(full))
    } else if (
      /\.(js|mjs|css|html)$/i.test(name) &&
      !/-legacy/.test(name)
    ) {
      out.push(full)
    }
  }
  return out
}

const files = walk(DIST)
const offences = []
for (const f of files) {
  const body = readFileSync(f, 'utf8')
  for (const token of BLOCKLIST) {
    if (body.includes(token)) {
      offences.push({ file: f, token })
    }
  }
}

if (offences.length) {
  console.error('[bundle-hygiene] forbidden strings found:')
  for (const { file, token } of offences) {
    console.error(`  ${token}  →  ${file}`)
  }
  process.exit(1)
}
console.log('[bundle-hygiene] clean (${files.length} files scanned)')
