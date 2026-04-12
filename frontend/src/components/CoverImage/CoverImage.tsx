import { useState } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  coverKey: string | null
  externalUrl?: string | null
  size?: number
  className?: string
}

export function CoverImage({ coverKey, externalUrl, size = 50, className }: Props) {
  const [failed, setFailed] = useState(false)
  const style = size ? { width: size, height: size } : undefined

  const src = coverKey
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(coverKey)}`
    : externalUrl ?? null

  return (
    <div className={`track-card-cover${className ? ` ${className}` : ''}`} style={style}>
      {src && !failed ? (
        <img
          src={src}
          alt=""
          onError={() => setFailed(true)}
        />
      ) : (
        <Icon name="music" size={size ? Math.round(size * 0.5) : 24} />
      )}
    </div>
  )
}
