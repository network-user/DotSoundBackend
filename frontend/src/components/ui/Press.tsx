import {
  forwardRef,
  useImperativeHandle,
  useRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from 'react'
import { useRipple } from './Ripple'

type Variant = 'default' | 'primary' | 'ghost' | 'icon'

interface Props
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  iconOnly?: boolean
  ripple?: boolean
  children?: ReactNode
}

const variantClass: Record<Variant, string> = {
  default: '',
  primary: 'press--primary',
  ghost: 'press--ghost',
  icon: 'press--icon',
}

/**
 * Accessible monochrome button with built-in tap target,
 * focus ring, pressed-state animation and (optional) ripple.
 * Defaults respect `prefers-reduced-motion`.
 */
export const Press = forwardRef<
  HTMLButtonElement,
  Props
>(function Press(
  {
    variant = 'default',
    iconOnly = false,
    ripple = true,
    className,
    type,
    children,
    ...rest
  },
  ref,
) {
  const innerRef = useRef<HTMLButtonElement>(null)
  useImperativeHandle(
    ref,
    () => innerRef.current as HTMLButtonElement,
  )
  useRipple(innerRef, { disabled: !ripple })

  const classes = [
    'press',
    iconOnly ? 'press--icon' : '',
    variantClass[variant],
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      ref={innerRef}
      type={type ?? 'button'}
      className={classes}
      {...rest}
    >
      {children}
    </button>
  )
})
