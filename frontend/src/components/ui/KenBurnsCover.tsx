import {
  m,
  useReducedMotion,
} from '@/lib/motion'

export interface KenBurnsCoverProps {
  src: string
  alt?: string
  duration?: number
  className?: string
}

export function KenBurnsCover({
  src,
  alt = '',
  duration = 18,
  className,
}: KenBurnsCoverProps) {
  const reduce = useReducedMotion()

  if (reduce) {
    return (
      <div
        className={[
          'kenburns-cover',
          'kenburns-cover--static',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <img
          src={src}
          alt={alt}
          loading="lazy"
        />
      </div>
    )
  }

  return (
    <div
      className={['kenburns-cover', className]
        .filter(Boolean)
        .join(' ')}
    >
      <m.img
        src={src}
        alt={alt}
        loading="lazy"
        animate={{
          scale: [1, 1.06, 1.02, 1.08, 1],
          x: [0, 6, -4, 4, 0],
          y: [0, -4, 6, -2, 0],
        }}
        transition={{
          duration,
          ease: 'easeInOut',
          repeat: Infinity,
        }}
      />
    </div>
  )
}
