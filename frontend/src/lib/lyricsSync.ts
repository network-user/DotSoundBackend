import type { SyncedLine, WordTime } from '@/types/api'

export function findActiveLineIndex(
  lines: readonly SyncedLine[],
  ms: number,
  hint: number = -1,
): number {
  if (lines.length === 0) return -1
  if (ms < lines[0].time_ms) return -1
  if (hint >= 0 && hint < lines.length) {
    const cur = lines[hint]
    const nxt = hint + 1 < lines.length ? lines[hint + 1] : null
    if (cur.time_ms <= ms && (!nxt || nxt.time_ms > ms)) {
      return hint
    }
    if (nxt && nxt.time_ms <= ms) {
      const after =
        hint + 2 < lines.length ? lines[hint + 2] : null
      if (!after || after.time_ms > ms) return hint + 1
    }
  }
  let lo = 0
  let hi = lines.length - 1
  let res = -1
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1
    if (lines[mid].time_ms <= ms) {
      res = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return res
}

export function findActiveWordIndex(
  words: readonly WordTime[] | null | undefined,
  ms: number,
  hint: number = -1,
): number {
  if (!words || words.length === 0) return -1
  if (hint >= 0 && hint < words.length) {
    const w = words[hint]
    if (ms >= w.start_ms && ms < w.start_ms + w.dur_ms) {
      return hint
    }
    if (hint + 1 < words.length) {
      const n = words[hint + 1]
      if (ms >= n.start_ms && ms < n.start_ms + n.dur_ms) {
        return hint + 1
      }
    }
  }
  for (let i = 0; i < words.length; i++) {
    const w = words[i]
    if (ms >= w.start_ms && ms < w.start_ms + w.dur_ms) {
      return i
    }
  }
  return -1
}

export function computeLineProgress(
  lines: readonly SyncedLine[],
  idx: number,
  ms: number,
  durationMs: number,
): number {
  if (idx < 0 || idx >= lines.length) return 0
  const cur = lines[idx]
  const next = lines[idx + 1]
  const endMs =
    next?.time_ms ??
    (durationMs > 0 ? durationMs : cur.time_ms + 3500)
  const span = Math.max(1, endMs - cur.time_ms)
  const p = (ms - cur.time_ms) / span
  return p < 0 ? 0 : p > 1 ? 1 : p
}

export function smoothScrollTop(
  el: HTMLElement,
  targetTop: number,
  durationMs: number = 320,
  reducedMotion: boolean | null = false,
): () => void {
  const start = el.scrollTop
  const dist = targetTop - start
  if (reducedMotion || Math.abs(dist) < 1) {
    el.scrollTop = targetTop
    return () => {}
  }
  let rafId = 0
  let cancelled = false
  const t0 =
    typeof performance !== 'undefined'
      ? performance.now()
      : Date.now()
  const ease = (t: number) =>
    t < 0.5
      ? 4 * t * t * t
      : 1 - Math.pow(-2 * t + 2, 3) / 2
  const step = (now: number) => {
    if (cancelled) return
    const elapsed = now - t0
    const t = Math.min(1, elapsed / durationMs)
    el.scrollTop = start + dist * ease(t)
    if (t < 1) rafId = requestAnimationFrame(step)
  }
  rafId = requestAnimationFrame(step)
  return () => {
    cancelled = true
    cancelAnimationFrame(rafId)
  }
}
