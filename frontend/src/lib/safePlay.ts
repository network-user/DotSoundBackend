export type SafePlayOpts = {
  onNotAllowed?: () => void
}

export function safePlay(
  audio: HTMLAudioElement,
  opts?: SafePlayOpts,
): Promise<void> {
  return audio.play().catch((e: unknown) => {
    const n =
      typeof e === 'object' &&
      e !== null &&
      'name' in e &&
      typeof (e as { name: unknown }).name ===
        'string'
        ? (e as { name: string }).name
        : ''
    if (n === 'AbortError') return
    if (n === 'NotAllowedError') {
      opts?.onNotAllowed?.()
      return
    }
  })
}

export function isBenignPlayError(
  e: unknown,
): boolean {
  const n =
    typeof e === 'object' &&
    e !== null &&
    'name' in e &&
    typeof (e as { name: unknown }).name ===
      'string'
      ? (e as { name: string }).name
      : ''
  return (
    n === 'AbortError' || n === 'NotAllowedError'
  )
}
