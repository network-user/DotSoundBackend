import type { SyncedLine } from '@/types/api'

export interface LrcParseResult {
  lines: SyncedLine[]
  metadata: {
    title?: string
    artist?: string
    album?: string
  }
}

const TIMETAG_RE = /\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]/g
const META_RE = /^\[(ti|ar|al|by|offset):\s*([^\]]*)\]$/i

export function parseLrc(text: string): LrcParseResult {
  const out: SyncedLine[] = []
  const metadata: LrcParseResult['metadata'] = {}
  let offsetMs = 0

  const rawLines = text.split(/\r?\n/)
  for (const raw of rawLines) {
    const line = raw.trim()
    if (!line) continue

    const meta = line.match(META_RE)
    if (meta) {
      const key = meta[1].toLowerCase()
      const value = meta[2].trim()
      if (key === 'ti') metadata.title = value
      else if (key === 'ar') metadata.artist = value
      else if (key === 'al') metadata.album = value
      else if (key === 'offset') {
        const parsed = Number.parseInt(value, 10)
        if (Number.isFinite(parsed)) offsetMs = parsed
      }
      continue
    }

    const stamps: number[] = []
    let lastIndex = 0
    let textPart = ''
    TIMETAG_RE.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = TIMETAG_RE.exec(line)) !== null) {
      stamps.push(stampToMs(match[1], match[2], match[3]))
      lastIndex = TIMETAG_RE.lastIndex
    }
    if (!stamps.length) continue
    textPart = line.slice(lastIndex).trim()
    for (const ms of stamps) {
      out.push({
        time_ms: Math.max(0, ms - offsetMs),
        text: textPart,
      })
    }
  }

  out.sort((a, b) => a.time_ms - b.time_ms)
  return { lines: out, metadata }
}

function stampToMs(
  mm: string,
  ss: string,
  frac: string | undefined,
): number {
  const minutes = Number.parseInt(mm, 10) || 0
  const seconds = Number.parseInt(ss, 10) || 0
  const fracStr = frac ?? '0'
  const fracPadded = fracStr.padEnd(3, '0').slice(0, 3)
  const millis = Number.parseInt(fracPadded, 10) || 0
  return minutes * 60_000 + seconds * 1000 + millis
}

export function looksLikeLrc(text: string): boolean {
  return /\[\d{1,2}:\d{1,2}/.test(text)
}
