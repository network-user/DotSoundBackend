interface Props {
  count?: number
}

export function SkeletonList({ count = 6 }: Props) {
  return (
    <div
      className="skeleton-list"
      aria-hidden="true"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-row">
          <div className="skeleton skeleton-cover" />
          <div className="skeleton-meta">
            <div className="skeleton skeleton-line skeleton-line--title" />
            <div className="skeleton skeleton-line skeleton-line--sub" />
          </div>
        </div>
      ))}
    </div>
  )
}
