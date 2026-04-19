import FingerprintJS from '@fingerprintjs/fingerprintjs'

let cached: Promise<string> | null = null

async function sha256Hex(value: string): Promise<string> {
  const data = new TextEncoder().encode(value)
  const buf = await crypto.subtle.digest(
    'SHA-256',
    data,
  )
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

function canvasFingerprint(): string {
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 220
    canvas.height = 30
    const ctx = canvas.getContext('2d')
    if (!ctx) return 'no-canvas'
    ctx.textBaseline = 'top'
    ctx.font = '14px "Arial"'
    ctx.fillStyle = '#f60'
    ctx.fillRect(125, 1, 62, 20)
    ctx.fillStyle = '#069'
    ctx.fillText('dotsound-admin', 2, 15)
    ctx.fillStyle = 'rgba(102, 204, 0, 0.7)'
    ctx.fillText('dotsound-admin', 4, 17)
    return canvas.toDataURL()
  } catch {
    return 'canvas-error'
  }
}

function webglFingerprint(): string {
  try {
    const canvas = document.createElement('canvas')
    const gl =
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl')
    if (!gl) return 'no-webgl'
    const debug = (
      gl as WebGLRenderingContext
    ).getExtension('WEBGL_debug_renderer_info')
    const vendor = debug
      ? (gl as WebGLRenderingContext).getParameter(
          (
            debug as { UNMASKED_VENDOR_WEBGL: number }
          ).UNMASKED_VENDOR_WEBGL,
        )
      : ''
    const renderer = debug
      ? (gl as WebGLRenderingContext).getParameter(
          (
            debug as {
              UNMASKED_RENDERER_WEBGL: number
            }
          ).UNMASKED_RENDERER_WEBGL,
        )
      : ''
    return `${vendor}|${renderer}`
  } catch {
    return 'webgl-error'
  }
}

export async function computeFingerprint(): Promise<string> {
  if (!cached) {
    cached = (async () => {
      const fp = await FingerprintJS.load()
      const result = await fp.get()
      const tz =
        Intl.DateTimeFormat().resolvedOptions()
          .timeZone || ''
      const lang = navigator.language || ''
      const seed = [
        result.visitorId,
        canvasFingerprint(),
        webglFingerprint(),
        tz,
        lang,
        navigator.userAgent,
      ].join('|')
      return sha256Hex(seed)
    })()
  }
  return cached
}
