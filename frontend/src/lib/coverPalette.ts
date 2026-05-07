export interface CoverPalette {
  tones: [string, string, string]
  text: 'light' | 'dark'
}

const cache = new Map<string, CoverPalette | null>()
const inflight = new Map<string, Promise<CoverPalette | null>>()

const SAMPLE_SIZE = 32

function rgbToHex(r: number, g: number, b: number): string {
  const h = (n: number) => n.toString(16).padStart(2, '0')
  return `#${h(r)}${h(g)}${h(b)}`
}

function hexToRgb(hex: string): [number, number, number] {
  const v = hex.replace('#', '')
  return [
    parseInt(v.slice(0, 2), 16),
    parseInt(v.slice(2, 4), 16),
    parseInt(v.slice(4, 6), 16),
  ]
}

function rgbToHsl(
  r: number,
  g: number,
  b: number,
): [number, number, number] {
  const rn = r / 255
  const gn = g / 255
  const bn = b / 255
  const max = Math.max(rn, gn, bn)
  const min = Math.min(rn, gn, bn)
  let h = 0
  let s = 0
  const l = (max + min) / 2
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case rn:
        h = (gn - bn) / d + (gn < bn ? 6 : 0)
        break
      case gn:
        h = (bn - rn) / d + 2
        break
      case bn:
        h = (rn - gn) / d + 4
        break
    }
    h *= 60
  }
  return [h, s, l]
}

function hslToRgb(
  h: number,
  s: number,
  l: number,
): [number, number, number] {
  if (s === 0) {
    const v = Math.round(l * 255)
    return [v, v, v]
  }
  const hue = ((h % 360) + 360) % 360 / 360
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  const f = (t: number) => {
    let tt = t
    if (tt < 0) tt += 1
    if (tt > 1) tt -= 1
    if (tt < 1 / 6) return p + (q - p) * 6 * tt
    if (tt < 1 / 2) return q
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6
    return p
  }
  return [
    Math.round(f(hue + 1 / 3) * 255),
    Math.round(f(hue) * 255),
    Math.round(f(hue - 1 / 3) * 255),
  ]
}

function desaturateHex(hex: string, target = 0.3): string {
  const [r, g, b] = hexToRgb(hex)
  const [h, s, l] = rgbToHsl(r, g, b)
  const ns = Math.min(s, target)
  const [nr, ng, nb] = hslToRgb(h, ns, l)
  return rgbToHex(nr, ng, nb)
}

function quantizeKey(r: number, g: number, b: number): number {
  return ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('image load failed'))
    img.src = url
  })
}

async function compute(url: string): Promise<CoverPalette | null> {
  if (typeof document === 'undefined') return null
  let img: HTMLImageElement
  try {
    img = await loadImage(url)
  } catch {
    return null
  }
  let canvas: HTMLCanvasElement
  let ctx: CanvasRenderingContext2D | null
  try {
    canvas = document.createElement('canvas')
    canvas.width = SAMPLE_SIZE
    canvas.height = SAMPLE_SIZE
    ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    ctx.drawImage(img, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  } catch {
    return null
  }

  let data: Uint8ClampedArray
  try {
    data = ctx.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE).data
  } catch {
    return null
  }

  const buckets = new Map<
    number,
    { r: number; g: number; b: number; count: number }
  >()
  let lumSum = 0
  let lumCount = 0
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i]
    const g = data[i + 1]
    const b = data[i + 2]
    const a = data[i + 3]
    if (a < 200) continue
    lumSum += 0.299 * r + 0.587 * g + 0.114 * b
    lumCount += 1
    const key = quantizeKey(r, g, b)
    const bucket = buckets.get(key)
    if (bucket) {
      bucket.r += r
      bucket.g += g
      bucket.b += b
      bucket.count += 1
    } else {
      buckets.set(key, { r, g, b, count: 1 })
    }
  }
  if (buckets.size === 0) return null

  const sorted = Array.from(buckets.values()).sort(
    (a, b) => b.count - a.count,
  )
  const top = sorted.slice(0, 3)
  while (top.length < 3) top.push(top[top.length - 1] ?? sorted[0])

  const tones = top.map((b) => {
    const r = Math.round(b.r / b.count)
    const g = Math.round(b.g / b.count)
    const bl = Math.round(b.b / b.count)
    return desaturateHex(rgbToHex(r, g, bl), 0.3)
  }) as [string, string, string]

  const avgLum = lumCount > 0 ? lumSum / lumCount : 128
  const text: 'light' | 'dark' = avgLum < 140 ? 'light' : 'dark'
  return { tones, text }
}

export async function extractCoverPalette(
  url: string | null | undefined,
): Promise<CoverPalette | null> {
  if (!url) return null
  if (cache.has(url)) return cache.get(url) ?? null
  const existing = inflight.get(url)
  if (existing) return existing
  const p = compute(url)
    .then((res) => {
      cache.set(url, res)
      inflight.delete(url)
      return res
    })
    .catch(() => {
      cache.set(url, null)
      inflight.delete(url)
      return null
    })
  inflight.set(url, p)
  return p
}

export function clearCoverPaletteCache(): void {
  cache.clear()
}
