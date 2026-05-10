async function loadImg(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

export async function createSharePoster(data: {
  totalMinutes: number
  headline: string
  minutesCaption: string
  brandLabel: string
  collageSrc: readonly string[]
}): Promise<Blob | null> {
  const W = 600
  const H = 800
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  ctx.fillStyle = '#141414'
  ctx.fillRect(0, 0, W, H)

  // 2×2 cover collage
  const tiles = Array.from(data.collageSrc).slice(0, 4)
  const cellW = W / 2
  const cellH = Math.round(H * 0.46)
  for (let i = 0; i < 4; i++) {
    const x = (i % 2) * cellW
    const y = Math.floor(i / 2) * cellH
    const src = tiles[i]
    if (src) {
      try {
        const img = await loadImg(src)
        ctx.drawImage(img, x, y, cellW, cellH)
      } catch {
        ctx.fillStyle = '#282828'
        ctx.fillRect(x, y, cellW, cellH)
      }
    } else {
      ctx.fillStyle = '#282828'
      ctx.fillRect(x, y, cellW, cellH)
    }
  }

  // Gradient fade over collage bottom
  const grad = ctx.createLinearGradient(0, H * 0.28, 0, H * 0.55)
  grad.addColorStop(0, 'rgba(20,20,20,0)')
  grad.addColorStop(1, 'rgba(20,20,20,1)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, W, H * 0.57)

  const FONT = '-apple-system, BlinkMacSystemFont, Arial, sans-serif'

  // Headline
  ctx.textAlign = 'center'
  ctx.fillStyle = 'rgba(255,255,255,0.55)'
  ctx.font = `400 22px ${FONT}`
  ctx.fillText(data.headline, W / 2, Math.round(H * 0.545))

  // Big minutes number
  const numSize = data.totalMinutes >= 10000 ? 80 : 96
  ctx.fillStyle = '#ffffff'
  ctx.font = `700 ${numSize}px ${FONT}`
  ctx.fillText(data.totalMinutes.toLocaleString(), W / 2, Math.round(H * 0.68))

  // Caption under number
  ctx.fillStyle = 'rgba(255,255,255,0.45)'
  ctx.font = `400 20px ${FONT}`
  ctx.fillText(data.minutesCaption, W / 2, Math.round(H * 0.755))

  // Thin divider
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(W * 0.22, Math.round(H * 0.845))
  ctx.lineTo(W * 0.78, Math.round(H * 0.845))
  ctx.stroke()

  // Brand watermark
  ctx.fillStyle = 'rgba(255,255,255,0.22)'
  ctx.font = `600 24px ${FONT}`
  ctx.fillText(data.brandLabel, W / 2, Math.round(H * 0.92))

  return new Promise<Blob | null>((res) =>
    canvas.toBlob((b) => res(b), 'image/png'),
  )
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
