import {
  forwardRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from 'react'

type Variant = 'default' | 'primary' | 'ghost' | 'icon'

interface Props
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  iconOnly?: boolean
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
 * focus ring and pressed-state animation. Defaults respect
 * `prefers-reduced-motion`.
 */
export const Press = forwardRef<
  HTMLButtonElement,
  Props
>(function Press(
  {
    variant = 'default',
    iconOnly = false,
    className,
    type,
    children,
    ...rest
  },
  ref,
) {
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
      ref={ref}
      type={type ?? 'button'}
      className={classes}
      {...rest}
    >
      {children}
    </button>
  )
})
