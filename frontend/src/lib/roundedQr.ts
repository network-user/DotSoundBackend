import QRCode from 'qrcode'

function readCssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') {
    return fallback
  }
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  return raw || fallback
}

function fillRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const rr = Math.min(r, w / 2, h / 2)
  if (rr <= 0) {
    ctx.fillRect(x, y, w, h)
    return
  }
  if (typeof ctx.roundRect === 'function') {
    ctx.beginPath()
    ctx.roundRect(x, y, w, h, rr)
    ctx.fill()
    return
  }
  ctx.beginPath()
  ctx.moveTo(x + rr, y)
  ctx.lineTo(x + w - rr, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr)
  ctx.lineTo(x + w, y + h - rr)
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h)
  ctx.lineTo(x + rr, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr)
  ctx.lineTo(x, y + rr)
  ctx.quadraticCurveTo(x, y, x + rr, y)
  ctx.closePath()
  ctx.fill()
}

export async function renderRoundedQrDataUrl(
  text: string,
  displaySize = 256,
): Promise<string | null> {
  if (typeof document === 'undefined') {
    return null
  }
  try {
    const qr = QRCode.create(text, {
      errorCorrectionLevel: 'Q',
    })
    const n = qr.modules.size
    const marginCells = 2
    const grid = n + marginCells * 2
    const cell = displaySize / grid
    const dpr = Math.min(
      2,
      typeof window !== 'undefined'
        ? window.devicePixelRatio || 1
        : 1,
    )
    const canvas = document.createElement('canvas')
    const px = Math.round(displaySize * dpr)
    canvas.width = px
    canvas.height = px
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      return null
    }
    ctx.scale(dpr, dpr)
    const bg = readCssVar('--bg-card', '#121214')
    const fg = readCssVar('--text', '#ececee')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, displaySize, displaySize)
    ctx.fillStyle = fg
    const gap = cell * 0.2
    const dot = cell - gap * 2
    const r = Math.max(0.8, dot * 0.42)
    for (let row = 0; row < n; row += 1) {
      for (let col = 0; col < n; col += 1) {
        if (!qr.modules.get(row, col)) {
          continue
        }
        const x = marginCells * cell + col * cell + gap
        const y = marginCells * cell + row * cell + gap
        fillRoundRect(ctx, x, y, dot, dot, r)
      }
    }
    return canvas.toDataURL('image/png')
  } catch {
    return null
  }
}
