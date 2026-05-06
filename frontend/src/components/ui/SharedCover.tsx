import {
  type ImgHTMLAttributes,
} from 'react'
import {
  m,
  SPRING_LAYOUT,
  useReducedMotion,
} from '@/lib/motion'

type ImgAttrs = Omit<
  ImgHTMLAttributes<HTMLImageElement>,
  | 'ref'
  | 'src'
  | 'onAnimationStart'
  | 'onAnimationEnd'
  | 'onAnimationIteration'
  | 'onDrag'
  | 'onDragStart'
  | 'onDragEnd'
  | 'onDragOver'
  | 'onDragEnter'
  | 'onDragLeave'
  | 'onDragExit'
  | 'onTransitionEnd'
>

export interface SharedCoverProps extends ImgAttrs {
  trackId: number | string | null | undefined
  src: string | null | undefined
  alt?: string
}

export function SharedCover({
  trackId,
  src,
  alt = '',
  className,
  ...rest
}: SharedCoverProps) {
  const reduce = useReducedMotion()
  const layoutId =
    trackId !== null && trackId !== undefined
      ? `cover-${trackId}`
      : undefined

  if (!src) {
    return (
      <div
        className={[
          'shared-cover',
          'shared-cover--empty',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
        aria-hidden="true"
      />
    )
  }

  return (
    <m.img
      layoutId={reduce ? undefined : layoutId}
      src={src}
      alt={alt}
      loading="lazy"
      className={['shared-cover', className]
        .filter(Boolean)
        .join(' ')}
      transition={reduce ? { duration: 0 } : SPRING_LAYOUT}
      {...rest}
    />
  )
}
