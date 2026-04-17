import { useCallback, useEffect, useSyncExternalStore } from 'react'
import { api } from '@/lib/api'

interface TaskState {
  taskId: string
  trackId: number
  generating: boolean
  stage: string | null
  genStatus: string | null
  startedAt: number
  debugLog: string[]
}

type Listener = () => void

let tasks = new Map<number, TaskState>()
const timers = new Map<number, ReturnType<typeof setInterval>>()
const listeners = new Set<Listener>()
let version = 0

function notify(): void {
  tasks = new Map(tasks)
  version++
  listeners.forEach((l) => l())
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function startPolling(trackId: number): void {
  if (timers.has(trackId)) return

  const timer = setInterval(async () => {
    const state = tasks.get(trackId)
    if (!state) {
      stopPolling(trackId)
      return
    }

    try {
      const { status, stage, logs } =
        await api.getLyricsAutoStatus(
          state.trackId,
          state.taskId,
        )

      const serverLogs = logs ?? []

      if (status === 'found') {
        stopPolling(trackId)
        tasks.set(trackId, {
          ...state,
          generating: false,
          genStatus: 'found',
          stage: stage ?? null,
          debugLog: serverLogs,
        })
        notify()
      } else if (
        status === 'not_found' ||
        status === 'error' ||
        status === 'cancelled'
      ) {
        stopPolling(trackId)
        tasks.set(trackId, {
          ...state,
          generating: false,
          genStatus: status,
          stage: stage ?? null,
          debugLog: serverLogs,
        })
        notify()
      } else {
        tasks.set(trackId, {
          ...state,
          stage: stage ?? state.stage,
          debugLog:
            serverLogs.length > 0
              ? serverLogs
              : state.debugLog,
        })
        notify()
      }
    } catch (err) {
      stopPolling(trackId)
      const msg =
        err instanceof Error
          ? err.message
          : 'polling failed'
      tasks.set(trackId, {
        ...state,
        generating: false,
        genStatus: 'error',
        stage: null,
        debugLog: [
          ...state.debugLog,
          `[client] ERROR: ${msg}`,
        ],
      })
      notify()
    }
  }, 2000)

  timers.set(trackId, timer)
}

function stopPolling(trackId: number): void {
  const timer = timers.get(trackId)
  if (timer) {
    clearInterval(timer)
    timers.delete(trackId)
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
    // Debug tier mode
    const response = await api.generateLyricsDebug(
      trackId,
      debugTier,
    )
    task_id = response.task_id
  } else {
    // Normal auto-generation
    const response = await api.generateLyrics(
      trackId,
      withSync ?? false,
    )
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
    startedAt: now,
    debugLog: [
      `[client] started (${modeLabel})`,
      `[client] progress_id=${task_id}`,
    ],
  })
  notify()

  startPolling(trackId)
}

function clearTask(trackId: number): void {
  stopPolling(trackId)
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
): void {
  tasks.set(trackId, {
    taskId,
    trackId,
    generating: true,
    stage: 'queued',
    genStatus: null,
    startedAt: Date.now(),
    debugLog: [
      '[client] redefine: old lyrics deleted',
      `[client] new task started, progress_id=${taskId}`,
    ],
  })
  notify()
  startPolling(trackId)
}

async function cancelGeneration(
  trackId: number,
): Promise<void> {
  const state = tasks.get(trackId)
  if (!state) return

  try {
    await api.cancelLyricsGeneration(trackId, state.taskId)
    tasks.set(trackId, {
      ...state,
      generating: false,
      genStatus: 'cancelled',
      debugLog: [
        ...state.debugLog,
        '[client] cancellation requested',
      ],
    })
    stopPolling(trackId)
    notify()
  } catch (err) {
    const msg =
      err instanceof Error ? err.message : 'cancel failed'
    tasks.set(trackId, {
      ...state,
      debugLog: [
        ...state.debugLog,
        `[client] ERROR cancelling: ${msg}`,
      ],
    })
    notify()
  }
}

function getSnapshot(): Map<number, TaskState> {
  return tasks
}

export function useLyricsTask(trackId: number) {
  const store = useSyncExternalStore(
    subscribe,
    getSnapshot,
  )

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
    (taskId: string) => {
      resumeTask(trackId, taskId)
    },
    [trackId],
  )

  useEffect(() => {
    if (
      state?.generating &&
      !timers.has(trackId)
    ) {
      startPolling(trackId)
    }
  }, [trackId, state?.generating])

  return {
    generating: state?.generating ?? false,
    stage: state?.stage ?? null,
    genStatus: state?.genStatus ?? null,
    taskId: state?.taskId ?? null,
    startedAt: state?.startedAt ?? 0,
    debugLog: state?.debugLog ?? [],
    startGeneration: start,
    clearTask: clear,
    clearDebugLog: clearLog,
    cancelGeneration: cancel,
    resumeTask: resume,
  }
}
