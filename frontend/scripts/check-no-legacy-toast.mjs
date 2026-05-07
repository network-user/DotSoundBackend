#!/usr/bin/env node
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const SRC = join(process.cwd(), 'src')
const ALLOWLIST = new Set([
  join('components', 'ui', 'Toast.tsx'),
])

const FORBIDDEN_PATTERNS = [
  /from\s+['"]@\/components\/ui\/Toast['"]/,
  /\buseToast\s*\(/,
  /\bToastProvider\b/,
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
      out.push(...walk(full))
      continue
    }
    if (/\.(ts|tsx|js|jsx)$/i.test(name)) {
      out.push(full)
    }
  }
  return out
}

const files = walk(SRC)
const violations = []

for (const file of files) {
  const relFromSrc = relative(SRC, file)
  if (ALLOWLIST.has(relFromSrc)) {
    continue
  }
  const body = readFileSync(file, 'utf8')
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (pattern.test(body)) {
      violations.push({
        file: relative(process.cwd(), file),
        pattern: pattern.toString(),
      })
    }
  }
}

if (violations.length > 0) {
  console.error('[no-legacy-toast] check failed:')
  for (const v of violations) {
    console.error(`  ${v.file} matches ${v.pattern}`)
  }
  console.error(
    'Use showIsland()/dismissIsland() from @/lib/island instead.',
  )
  process.exit(1)
}

console.log(
  `[no-legacy-toast] check passed (${files.length} files scanned)`,
)
