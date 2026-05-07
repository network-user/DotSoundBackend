export type IslandKind = 'toast' | 'progress' | 'now-playing' | 'error'

export interface IslandPayload {
  kind: IslandKind
  title: string
  hint?: string
  iconName?: string
  progress?: number
  onClick?: () => void
  durationMs?: number
}

export interface IslandEntry extends IslandPayload {
  id: string
  createdAt: number
}

type Listener = (entries: IslandEntry[]) => void

let entries: IslandEntry[] = []
const listeners = new Set<Listener>()
const timers = new Map<string, ReturnType<typeof setTimeout>>()
let counter = 0

function notify() {
  for (const fn of listeners) fn(entries.slice())
}

function makeId(): string {
  counter += 1
  return `island-${Date.now().toString(36)}-${counter}`
}

const DEFAULT_DURATION_MS: Record<IslandKind, number | undefined> = {
  toast: 3000,
  progress: undefined,
  'now-playing': undefined,
  error: undefined,
}

export function showIsland(payload: IslandPayload): string {
  const id = makeId()
  const entry: IslandEntry = {
    ...payload,
    id,
    createdAt: Date.now(),
  }
  entries = [...entries, entry]
  const duration = payload.durationMs ?? DEFAULT_DURATION_MS[payload.kind]
  if (duration && Number.isFinite(duration) && duration > 0) {
    const t = setTimeout(() => dismissIsland(id), duration)
    timers.set(id, t)
  }
  notify()
  return id
}

export function updateIsland(
  id: string,
  patch: Partial<IslandPayload>,
): void {
  let changed = false
  entries = entries.map((e) => {
    if (e.id !== id) return e
    changed = true
    return { ...e, ...patch }
  })
  if (changed) notify()
}

export function dismissIsland(id?: string): void {
  if (id) {
    const t = timers.get(id)
    if (t) {
      clearTimeout(t)
      timers.delete(id)
    }
    const before = entries.length
    entries = entries.filter((e) => e.id !== id)
    if (entries.length !== before) notify()
    return
  }
  for (const t of timers.values()) clearTimeout(t)
  timers.clear()
  if (entries.length > 0) {
    entries = []
    notify()
  }
}

export function subscribeIsland(listener: Listener): () => void {
  listeners.add(listener)
  listener(entries.slice())
  return () => {
    listeners.delete(listener)
  }
}

export function getIslandSnapshot(): IslandEntry[] {
  return entries.slice()
}
