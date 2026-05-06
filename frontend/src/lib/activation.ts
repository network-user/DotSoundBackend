const STORAGE_KEY = 'activation:firstAuthAt'
const FIRST_PLAY_KEY = 'activation:firstPlayAt'
const SENT_KEY = 'activation:sent'

export type ActivationEvent =
  | 'auth_success'
  | 'onboarding_step_view'
  | 'onboarding_step_complete'
  | 'onboarding_skip'
  | 'onboarding_complete'
  | 'home_first_play'
  | 'home_first_session_start'
  | 'home_play_all'
  | 'home_start_radio'

interface EmitOptions {
  meta?: Record<string, string | number | boolean | null>
  once?: boolean
}

function readSentSet(): Set<string> {
  try {
    const raw = sessionStorage.getItem(SENT_KEY)
    if (!raw) return new Set()
    return new Set(JSON.parse(raw) as string[])
  } catch {
    return new Set()
  }
}

function writeSentSet(set: Set<string>): void {
  try {
    sessionStorage.setItem(
      SENT_KEY,
      JSON.stringify(Array.from(set)),
    )
  } catch {
    /* ignore */
  }
}

export function markAuthSuccess(): void {
  try {
    if (!localStorage.getItem(STORAGE_KEY)) {
      localStorage.setItem(
        STORAGE_KEY,
        String(Date.now()),
      )
    }
  } catch {
    /* ignore */
  }
}

function getElapsedFromAuthMs(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const ts = Number(raw)
    if (!Number.isFinite(ts)) return null
    return Date.now() - ts
  } catch {
    return null
  }
}

function postEvent(
  name: ActivationEvent,
  meta: Record<string, string | number | boolean | null>,
): void {
  try {
    const blob = new Blob(
      [JSON.stringify({ event: name, meta })],
      { type: 'application/json' },
    )
    const sent = navigator.sendBeacon?.(
      '/api/v1/onboarding/activation-event',
      blob,
    )
    if (!sent) {
      void fetch('/api/v1/onboarding/activation-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: name, meta }),
        keepalive: true,
      }).catch(() => {})
    }
  } catch {
    /* best-effort */
  }
}

export function trackActivationEvent(
  name: ActivationEvent,
  options: EmitOptions = {},
): void {
  const meta: Record<string, string | number | boolean | null> = {
    ...(options.meta ?? {}),
  }

  if (name === 'home_first_play' || name === 'home_first_session_start') {
    try {
      const already = localStorage.getItem(FIRST_PLAY_KEY)
      if (!already) {
        localStorage.setItem(
          FIRST_PLAY_KEY,
          String(Date.now()),
        )
        const elapsed = getElapsedFromAuthMs()
        if (elapsed != null) {
          meta.ms_from_auth = Math.round(elapsed)
        }
      }
    } catch {
      /* ignore */
    }
  }

  if (options.once) {
    const sent = readSentSet()
    if (sent.has(name)) return
    sent.add(name)
    writeSentSet(sent)
  }

  if (
    typeof console !== 'undefined' &&
    typeof console.info === 'function'
  ) {
    console.info('[activation]', name, meta)
  }

  postEvent(name, meta)
}
