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
    const r = cell * 0.56
    const x0 = marginCells * cell + cell / 2
    const y0 = marginCells * cell + cell / 2
    ctx.fillStyle = fg
    for (let row = 0; row < n; row += 1) {
      for (let col = 0; col < n; col += 1) {
        if (!qr.modules.get(row, col)) {
          continue
        }
        const cx = x0 + col * cell
        const cy = y0 + row * cell
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, Math.PI * 2)
        ctx.fill()
      }
    }
    return canvas.toDataURL('image/png')
  } catch {
    return null
  }
}
