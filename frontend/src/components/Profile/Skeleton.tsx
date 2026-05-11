import type { CSSProperties } from 'react'

interface SkelProps {
  width?: number | string
  height?: number | string
  className?: string
  style?: CSSProperties
}

export function Skel({
  width,
  height,
  className,
  style,
}: SkelProps) {
  const merged: CSSProperties = {
    width: width ?? '100%',
    height: height ?? 12,
    ...style,
  }
  return (
    <span
      aria-hidden
      className={`rp-skel${className ? ` ${className}` : ''}`}
      style={merged}
    />
  )
}

export function SkelCircle({ size = 36 }: { size?: number }) {
  return (
    <Skel
      className="rp-skel--circle"
      width={size}
      height={size}
    />
  )
}

export function SkelText({
  width = '60%',
  size = 'sm',
}: {
  width?: number | string
  size?: 'sm' | 'lg'
}) {
  return (
    <Skel
      className={
        size === 'lg' ? 'rp-skel--text-lg' : 'rp-skel--text'
      }
      width={width}
    />
  )
}

/* Composed skeletons ------------------------------------------ */

export function StatsRowSkeleton() {
  return (
    <div className="profile-stats" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div className="stat-item" key={i}>
          <SkelText width={56} size="lg" />
          <div style={{ marginTop: 8 }}>
            <SkelText width={70} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function TrackRowSkeleton() {
  return (
    <div
      aria-hidden
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 14px',
      }}
    >
      <Skel width={48} height={48} style={{ borderRadius: 8 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <SkelText width="65%" size="lg" />
        <div style={{ marginTop: 6 }}>
          <SkelText width="40%" />
        </div>
      </div>
    </div>
  )
}
