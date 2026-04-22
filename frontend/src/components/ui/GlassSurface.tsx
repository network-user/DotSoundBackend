import {
  forwardRef,
  useEffect,
  useRef,
  type CSSProperties,
  type HTMLAttributes,
  type ReactNode,
} from 'react'

type Intensity = 'subtle' | 'medium' | 'strong' | 'liquid'
type Tint = 'neutral' | 'accent'

interface Props
  extends HTMLAttributes<HTMLDivElement> {
  intensity?: Intensity
  tint?: Tint
  interactive?: boolean
  bordered?: boolean
  noiseOverlay?: boolean
  children?: ReactNode
}

const intensityClass: Record<Intensity, string> = {
  subtle: 'glass--subtle',
  medium: 'glass--medium',
  strong: 'glass--strong',
  liquid: 'glass--liquid',
}

const tintClass: Record<Tint, string> = {
  neutral: 'glass--tint-neutral',
  accent: 'glass--tint-accent',
}

/**
 * Frosted-glass surface primitive with optional cursor-following
 * highlight (interactive) and turbulent noise overlay. Pure CSS
 * + tiny pointer listener; no WebGL or external libs.
 */
export const GlassSurface = forwardRef<
  HTMLDivElement,
  Props
>(function GlassSurface(
  {
    intensity = 'medium',
    tint = 'neutral',
    interactive = false,
    bordered = true,
    noiseOverlay = false,
    className,
    children,
    style,
    ...rest
  },
  ref,
) {
  const localRef = useRef<HTMLDivElement | null>(null)
  const setRefs = (el: HTMLDivElement | null) => {
    localRef.current = el
    if (typeof ref === 'function') ref(el)
    else if (ref)
      (
        ref as React.MutableRefObject<HTMLDivElement | null>
      ).current = el
  }

  useEffect(() => {
    if (!interactive) return
    const el = localRef.current
    if (!el) return
    const handle = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect()
      const x =
        ((e.clientX - rect.left) / rect.width) * 100
      const y =
        ((e.clientY - rect.top) / rect.height) * 100
      el.style.setProperty('--gx', `${x}%`)
      el.style.setProperty('--gy', `${y}%`)
    }
    const reset = () => {
      el.style.setProperty('--gx', `50%`)
      el.style.setProperty('--gy', `0%`)
    }
    el.addEventListener('pointermove', handle)
    el.addEventListener('pointerleave', reset)
    reset()
    return () => {
      el.removeEventListener('pointermove', handle)
      el.removeEventListener('pointerleave', reset)
    }
  }, [interactive])

  const classes = [
    'glass',
    intensityClass[intensity],
    tintClass[tint],
    interactive ? 'glass--interactive' : '',
    bordered ? 'glass--bordered' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')

  const merged: CSSProperties = style ?? {}

  return (
    <div
      ref={setRefs}
      className={classes}
      style={merged}
      {...rest}
    >
      <span
        aria-hidden="true"
        className="glass__highlight"
      />
      {noiseOverlay && (
        <span
          aria-hidden="true"
          className="glass__noise"
        />
      )}
      <span className="glass__content">{children}</span>
    </div>
  )
})
