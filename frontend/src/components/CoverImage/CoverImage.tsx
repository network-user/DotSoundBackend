import { useState, type CSSProperties } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  coverKey: string | null
  externalUrl?: string | null
  size?: number
  className?: string
  style?: CSSProperties
}

const COVER_RENDER_WIDTHS = [120, 240, 480] as const

function buildProxyUrl(
  key: string,
  width?: number,
): string {
  const base = `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
  return width ? `${base}&w=${width}` : base
}

function buildSrcSet(key: string): string {
  return COVER_RENDER_WIDTHS.map(
    (w) => `${buildProxyUrl(key, w)} ${w}w`,
  ).join(', ')
}

function pickSizesAttr(displaySize: number): string {
  return `${displaySize}px`
}

export function CoverImage({
  coverKey,
  externalUrl,
  size = 56,
  className,
  style,
}: Props) {
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const sizeStyle = size
    ? { width: size, height: size }
    : undefined
  const mergedStyle = style
    ? { ...sizeStyle, ...style }
    : sizeStyle

  const proxySrc = coverKey ? buildProxyUrl(coverKey) : null
  const srcSet = coverKey ? buildSrcSet(coverKey) : undefined
  const sizesAttr = coverKey ? pickSizesAttr(size) : undefined
  const src = proxySrc ?? externalUrl ?? null

  return (
    <div
      className={`track-card-cover${className ? ` ${className}` : ''}${loaded ? ' loaded' : ''}`}
      style={mergedStyle}
    >
      {src && !failed ? (
        <img
          src={src}
          srcSet={srcSet}
          sizes={sizesAttr}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          onLoad={() => setLoaded(true)}
        />
      ) : (
        <Icon
          name="music"
          size={size ? Math.round(size * 0.5) : 24}
        />
      )}
    </div>
  )
}
