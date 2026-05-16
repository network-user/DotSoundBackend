import {
  useEffect,
  useState,
  type CSSProperties,
  type ImgHTMLAttributes,
} from 'react'
import { Icon } from '@/components/Icon/Icon'
import {
  coverProxySizes,
  coverProxySrcSet,
  coverProxyUrl,
  pickCoverRenderWidth,
} from '@/lib/coverProxy'

interface Props {
  coverKey: string | null
  externalUrl?: string | null
  size?: number
  className?: string
  style?: CSSProperties
  loading?: ImgHTMLAttributes<HTMLImageElement>['loading']
}

export function CoverImage({
  coverKey,
  externalUrl,
  size = 56,
  className,
  style,
  loading = 'lazy',
}: Props) {
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const sizeStyle = size
    ? { width: size, height: size }
    : undefined
  const mergedStyle = style
    ? { ...sizeStyle, ...style }
    : sizeStyle

  const renderWidth = pickCoverRenderWidth(size)
  const proxySrc = coverKey
    ? coverProxyUrl(coverKey, { width: renderWidth })
    : null
  const srcSet = coverKey ? coverProxySrcSet(coverKey) : undefined
  const sizesAttr = coverKey ? coverProxySizes(size) : undefined
  const src = proxySrc ?? externalUrl ?? null

  useEffect(() => {
    setFailed(false)
    setLoaded(false)
  }, [src])

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
          loading={loading}
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
