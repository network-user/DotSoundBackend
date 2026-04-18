import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

interface ConfirmApi {
  /** True while we're waiting for the second tap. */
  pending: boolean
  /** Begin the confirmation window. */
  request: () => void
  /** Confirm — resets state and runs the callback. */
  confirm: () => void
  /** Cancel — resets state without running anything. */
  cancel: () => void
}

/**
 * Two-tap confirmation primitive for destructive actions.
 *
 * Usage:
 *   const { pending, request, confirm } = useConfirm(
 *     () => api.deleteTrack(id),
 *   )
 *   <button onClick={pending ? confirm : request}>
 *     {pending ? 'Точно удалить?' : 'Удалить'}
 *   </button>
 *
 * The internal timer is cleared automatically on unmount.
 */
export function useConfirm(
  onConfirmed: () => void,
  timeoutMs = 3000,
): ConfirmApi {
  const [pending, setPending] = useState(false)
  const timerRef = useRef<ReturnType<
    typeof setTimeout
  > | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => clearTimer, [clearTimer])

  const request = useCallback(() => {
    clearTimer()
    setPending(true)
    timerRef.current = setTimeout(() => {
      setPending(false)
      timerRef.current = null
    }, timeoutMs)
  }, [clearTimer, timeoutMs])

  const confirm = useCallback(() => {
    if (!pending) return
    clearTimer()
    setPending(false)
    onConfirmed()
  }, [pending, onConfirmed, clearTimer])

  const cancel = useCallback(() => {
    clearTimer()
    setPending(false)
  }, [clearTimer])

  return { pending, request, confirm, cancel }
}
