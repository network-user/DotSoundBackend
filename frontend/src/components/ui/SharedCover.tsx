import {
  useEffect,
  useState,
  type ImgHTMLAttributes,
} from 'react'
import {
  m,
  SPRING_LAYOUT,
  useReducedMotion,
} from '@/lib/motion'
import { Icon } from '@/components/Icon/Icon'

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
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)
  const layoutId =
    trackId !== null && trackId !== undefined
      ? `cover-${trackId}`
      : undefined

  useEffect(() => {
    setLoaded(false)
    setErrored(false)
  }, [src])

  if (!src || errored) {
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
      >
        <span className="shared-cover__empty-icon">
          <Icon name="music" size={20} />
        </span>
      </div>
    )
  }

  return (
    <div
      className={[
        'shared-cover',
        'shared-cover-frame',
        loaded ? 'shared-cover-frame--loaded' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <m.img
        layoutId={reduce ? undefined : layoutId}
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        className="shared-cover-frame__img"
        transition={reduce ? { duration: 0 } : SPRING_LAYOUT}
        onLoad={() => setLoaded(true)}
        onError={() => {
          setErrored(true)
          setLoaded(true)
        }}
        {...rest}
      />
    </div>
  )
}
