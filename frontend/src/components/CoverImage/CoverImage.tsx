interface Props {
  coverKey: string | null
  size?: number
  className?: string
}

export function CoverImage({ coverKey, size = 50, className }: Props) {
  const style = size ? { width: size, height: size } : undefined

  return (
    <div className={`track-card-cover${className ? ` ${className}` : ''}`} style={style}>
      {coverKey ? (
        <img
          src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(coverKey)}`}
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
