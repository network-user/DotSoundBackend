import type HlsDefault from 'hls.js'

export type HlsPlayer = InstanceType<typeof HlsDefault>

let hlsClassPromise: Promise<typeof HlsDefault> | null = null

export function loadHlsClass(): Promise<typeof HlsDefault> {
  if (!hlsClassPromise) {
    hlsClassPromise = import('hls.js').then((m) => m.default)
  }
  return hlsClassPromise
}
