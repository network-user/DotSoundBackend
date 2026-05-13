import {
  m,
  useReducedMotion,
} from '@/lib/motion'

export type KenBurnsMotion = 'pan' | 'breathe'

export interface KenBurnsCoverProps {
  src: string
  srcSet?: string
  alt?: string
  duration?: number
  className?: string
  active?: boolean
  motion?: KenBurnsMotion
}

export function KenBurnsCover({
  src,
  srcSet,
  alt = '',
  duration = 18,
  className,
  active = true,
  motion = 'pan',
}: KenBurnsCoverProps) {
  const reduce = useReducedMotion()

  if (reduce || !active) {
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
          srcSet={srcSet}
          sizes={srcSet ? 'min(92vw, 480px)' : undefined}
          alt={alt}
          loading="eager"
          fetchPriority="high"
          draggable={false}
        />
      </div>
    )
  }

  if (motion === 'breathe') {
    const breatheDur = Math.min(
      8.5,
      Math.max(4.2, duration * 0.32),
    )
    return (
      <div
        className={[
          'kenburns-cover',
          'kenburns-cover--breathe',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <m.img
          src={src}
          srcSet={srcSet}
          sizes={srcSet ? 'min(92vw, 480px)' : undefined}
          alt={alt}
          loading="eager"
          fetchPriority="high"
          draggable={false}
          animate={{
            scale: [1, 1.038, 1.014, 1.042, 1],
          }}
          transition={{
            duration: breatheDur,
            ease: 'easeInOut',
            repeat: Infinity,
          }}
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
        srcSet={srcSet}
        sizes={srcSet ? 'min(92vw, 480px)' : undefined}
        alt={alt}
        loading="eager"
        fetchPriority="high"
        draggable={false}
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
