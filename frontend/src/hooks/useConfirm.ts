import { useState, useCallback } from 'react'

export function useConfirm(onConfirmed: () => void, timeoutMs = 3000) {
  const [pending, setPending] = useState(false)

  const request = useCallback(() => {
    setPending(true)
    const t = setTimeout(() => setPending(false), timeoutMs)
    return () => clearTimeout(t)
  }, [timeoutMs])

  const confirm = useCallback(() => {
    if (!pending) return
    setPending(false)
    onConfirmed()
  }, [pending, onConfirmed])

  const cancel = useCallback(() => setPending(false), [])

  return { pending, request, confirm, cancel }
}
