import { useCallback, useEffect, useSyncExternalStore } from 'react'
import { api } from '@/lib/api'

interface TaskState {
  taskId: string
  trackId: number
  generating: boolean
  stage: string | null
  genStatus: string | null
  percent: number | null
  startedAt: number
  debugLog: string[]
}

type Listener = () => void

const TERMINAL = new Set(['found', 'not_found', 'error', 'cancelled'])
const POLLING_INTERVAL_MS = 2000

let tasks = new Map<number, TaskState>()
const pollTimers = new Map<number, ReturnType<typeof setInterval>>()
const eventSources = new Map<number, EventSource>()
const listeners = new Set<Listener>()

function notify(): void {
  tasks = new Map(tasks)
  listeners.forEach((l) => l())
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function stopSubscription(trackId: number): void {
  const es = eventSources.get(trackId)
  if (es) {
    try {
      es.close()
    } catch {}
    eventSources.delete(trackId)
  }
  const timer = pollTimers.get(trackId)
  if (timer) {
    clearInterval(timer)
    pollTimers.delete(trackId)
  }
}

function appendClientLog(trackId: number, line: string): void {
  const state = tasks.get(trackId)
  if (!state) return
  tasks.set(trackId, {
    ...state,
    debugLog: [...state.debugLog, line],
  })
  notify()
}

function appendDebugLog(trackId: number, line: string): void {
  appendClientLog(trackId, line)
}

function applyPayload(
  trackId: number,
  payload: {
    status?: string
    stage?: string | null
    terminal_state?: string | null
    percent?: number | null
    log?: string
    logs?: string[]
  },
): void {
  const state = tasks.get(trackId)
  if (!state) return

  const terminal =
    payload.terminal_state ??
    (payload.status && TERMINAL.has(payload.status) ? payload.status : null)

  const nextStage =
    payload.stage !== undefined ? (payload.stage ?? null) : state.stage

  const nextPercent =
    payload.percent !== undefined && payload.percent !== null
      ? Math.max(0, Math.min(100, Math.round(payload.percent)))
      : state.percent

  let nextLogs = state.debugLog
  if (payload.logs && payload.logs.length > 0) {
    nextLogs = payload.logs
  } else if (payload.log) {
    nextLogs = [...state.debugLog, payload.log]
  }

  if (terminal) {
    tasks.set(trackId, {
      ...state,
      generating: false,
      genStatus: terminal,
      stage: nextStage,
      percent: terminal === 'found' ? 100 : nextPercent,
      debugLog: nextLogs,
    })
    stopSubscription(trackId)
  } else {
    tasks.set(trackId, {
      ...state,
      stage: nextStage,
      percent: nextPercent,
      debugLog: nextLogs,
    })
  }
  notify()
}

function startPolling(trackId: number): void {
  if (pollTimers.has(trackId)) return

  const timer = setInterval(async () => {
    const state = tasks.get(trackId)
    if (!state) {
      stopSubscription(trackId)
      return
    }

    try {
      const resp = await api.getLyricsAutoStatus(
        state.trackId,
        state.taskId,
      )
      applyPayload(trackId, {
        status: resp.status,
        stage: resp.stage ?? null,
        percent: resp.percent ?? null,
        logs: resp.logs ?? [],
      })
    } catch (err) {
      stopSubscription(trackId)
      const msg = err instanceof Error ? err.message : 'polling failed'
      const current = tasks.get(trackId)
      if (current) {
        tasks.set(trackId, {
          ...current,
          generating: false,
          genStatus: 'error',
          stage: null,
          debugLog: [...current.debugLog, `[client] ERROR: ${msg}`],
        })
        notify()
      }
    }
  }, POLLING_INTERVAL_MS)

  pollTimers.set(trackId, timer)
}

function startSubscription(trackId: number): void {
  if (eventSources.has(trackId) || pollTimers.has(trackId)) return

  const state = tasks.get(trackId)
  if (!state) return

  const supportsSSE =
    typeof window !== 'undefined' && typeof window.EventSource !== 'undefined'

  if (!supportsSSE) {
    startPolling(trackId)
    return
  }

  try {
    const url = api.lyricsAutoEventsUrl(state.trackId, state.taskId)
    const es = new EventSource(url, { withCredentials: true })

    const onMessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data as string)
        applyPayload(trackId, {
          stage: data.stage ?? null,
          percent: data.percent ?? null,
          terminal_state: data.terminal_state ?? null,
          log: data.log ?? undefined,
        })
      } catch {}
    }

    es.addEventListener('snapshot', onMessage)
    es.addEventListener('progress', onMessage)
    es.addEventListener('error', () => {
      try {
        es.close()
      } catch {}
      eventSources.delete(trackId)
      const cur = tasks.get(trackId)
      if (cur?.generating) {
        appendClientLog(trackId, '[client] SSE disconnected, polling')
        startPolling(trackId)
      }
    })

    eventSources.set(trackId, es)
  } catch {
    startPolling(trackId)
  }
}

async function startGeneration(
  trackId: number,
  withSync?: boolean,
  debugTier?: number,
): Promise<void> {
  const now = Date.now()
  let task_id: string

  if (debugTier) {
    const response = await api.generateLyricsDebug(trackId, debugTier)
    task_id = response.task_id
  } else {
    const response = await api.generateLyrics(trackId, withSync ?? false)
    task_id = response.task_id
  }

  const modeLabel = debugTier
    ? `DEBUG stage=${debugTier}`
    : `AUTO (withSync=${withSync})`

  tasks.set(trackId, {
    taskId: task_id,
    trackId,
    generating: true,
    stage: 'queued',
    genStatus: null,
    percent: 0,
    startedAt: now,
    debugLog: [
      `[client] started (${modeLabel}) track_id=${trackId}`,
      `[client] progress_id=${task_id}`,
    ],
  })
  notify()
  startSubscription(trackId)
}

function clearTask(trackId: number): void {
  stopSubscription(trackId)
  tasks.delete(trackId)
  notify()
}

function clearDebugLog(trackId: number): void {
  const state = tasks.get(trackId)
  if (!state) return
  tasks.set(trackId, {
    ...state,
    debugLog: [],
  })
  notify()
}

function resumeTask(
  trackId: number,
  taskId: string,
  options?: {
    withSync?: boolean
    bypassCache?: boolean
  },
): void {
  const withSync = options?.withSync ?? false
  const bypassCache = options?.bypassCache ?? false
  tasks.set(trackId, {
    taskId,
    trackId,
    generating: true,
    stage: 'queued',
    genStatus: null,
    percent: 0,
    startedAt: Date.now(),
    debugLog: [
      '[client] redefine accepted by backend',
      `[client] request: with_sync=${withSync} | bypass_cache=${bypassCache}`,
      `[client] progress_id=${taskId}`,
    ],
  })
  notify()
  startSubscription(trackId)
}

async function cancelGeneration(trackId: number): Promise<void> {
  const state = tasks.get(trackId)
  if (!state) return

  try {
    await api.cancelLyricsGeneration(trackId, state.taskId)
    const cur = tasks.get(trackId)
    if (cur) {
      tasks.set(trackId, {
        ...cur,
        generating: false,
        genStatus: 'cancelled',
        debugLog: [...cur.debugLog, '[client] cancellation requested'],
      })
      stopSubscription(trackId)
      notify()
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'cancel failed'
    const cur = tasks.get(trackId)
    if (cur) {
      tasks.set(trackId, {
        ...cur,
        debugLog: [...cur.debugLog, `[client] ERROR cancelling: ${msg}`],
      })
      notify()
    }
  }
}

function getSnapshot(): Map<number, TaskState> {
  return tasks
}

export function useLyricsTask(trackId: number) {
  const store = useSyncExternalStore(subscribe, getSnapshot)

  const state = store.get(trackId)

  const start = useCallback(
    async (withSync?: boolean, debugTier?: number) => {
      await startGeneration(trackId, withSync, debugTier)
    },
    [trackId],
  )

  const clear = useCallback(() => {
    clearTask(trackId)
  }, [trackId])

  const clearLog = useCallback(() => {
    clearDebugLog(trackId)
  }, [trackId])

  const cancel = useCallback(async () => {
    await cancelGeneration(trackId)
  }, [trackId])

  const resume = useCallback(
    (
      taskId: string,
      options?: {
        withSync?: boolean
        bypassCache?: boolean
      },
    ) => {
      resumeTask(trackId, taskId, options)
    },
    [trackId],
  )

  const appendLog = useCallback(
    (line: string) => {
      appendDebugLog(trackId, line)
    },
    [trackId],
  )

  useEffect(() => {
    if (
      state?.generating &&
      !eventSources.has(trackId) &&
      !pollTimers.has(trackId)
    ) {
      startSubscription(trackId)
    }
  }, [trackId, state?.generating])

  return {
    generating: state?.generating ?? false,
    stage: state?.stage ?? null,
    genStatus: state?.genStatus ?? null,
    percent: state?.percent ?? null,
    taskId: state?.taskId ?? null,
    startedAt: state?.startedAt ?? 0,
    debugLog: state?.debugLog ?? [],
    startGeneration: start,
    clearTask: clear,
    clearDebugLog: clearLog,
    cancelGeneration: cancel,
    resumeTask: resume,
    appendDebugLog: appendLog,
  }
}
