import { useState, type CSSProperties } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  coverKey: string | null
  externalUrl?: string | null
  size?: number
  className?: string
  style?: CSSProperties
}

export function CoverImage({
  coverKey,
  externalUrl,
  size = 50,
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

  const src = coverKey
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(coverKey)}`
    : externalUrl ?? null

  return (
    <div
      className={`track-card-cover${className ? ` ${className}` : ''}${loaded ? ' loaded' : ''}`}
      style={mergedStyle}
    >
      {src && !failed ? (
        <img
          src={src}
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
