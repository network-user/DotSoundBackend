interface Props {
  coverKey: string | null
  externalUrl?: string | null
  size?: number
  className?: string
}

export function CoverImage({ coverKey, externalUrl, size = 50, className }: Props) {
  const style = size ? { width: size, height: size } : undefined

  const src = coverKey
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(coverKey)}`
    : externalUrl ?? null

  return (
    <div className={`track-card-cover${className ? ` ${className}` : ''}`} style={style}>
      {src ? (
        <img
          src={src}
          alt=""
          onError={(e) => {
            const parent = (e.target as HTMLImageElement).parentElement
            if (parent) parent.textContent = '🎵'
          }}
        />
      ) : (
        '🎵'
      )}
    </div>
  )
}
