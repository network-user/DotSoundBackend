export const COVER_RENDER_WIDTHS = [120, 240, 480] as const

export type CoverRenderWidth = (typeof COVER_RENDER_WIDTHS)[number]

export interface CoverProxyOptions {
  width?: CoverRenderWidth
  version?: number | string | null
}

export function pickCoverRenderWidth(
  displaySize: number,
): CoverRenderWidth {
  const dpr =
    typeof window === 'undefined'
      ? 1
      : Math.min(window.devicePixelRatio || 1, 2)
  const target = Math.max(1, displaySize * dpr)
  return (
    COVER_RENDER_WIDTHS.find((width) => width >= target) ??
    COVER_RENDER_WIDTHS[COVER_RENDER_WIDTHS.length - 1]
  )
}

export function coverProxyUrl(
  imageKey: string,
  options: CoverProxyOptions = {},
): string {
  const params = [`key=${encodeURIComponent(imageKey)}`]
  if (options.version !== undefined && options.version !== null) {
    params.push(`v=${encodeURIComponent(String(options.version))}`)
  }
  if (options.width) {
    params.push(`w=${options.width}`)
  }
  return `/api/v1/tracks/cover_proxy?${params.join('&')}`
}

export function coverProxySrcSet(
  imageKey: string,
  version?: number | string | null,
): string {
  return COVER_RENDER_WIDTHS.map(
    (width) =>
      `${coverProxyUrl(imageKey, { version, width })} ${width}w`,
  ).join(', ')
}

export function coverProxySizes(displaySize: number): string {
  return `${displaySize}px`
}
