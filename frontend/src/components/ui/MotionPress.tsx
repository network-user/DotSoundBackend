import {
  type ButtonHTMLAttributes,
  type ReactNode,
  forwardRef,
} from 'react'
import {
  m,
  SPRING_PRESS,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import {
  haptic,
  hapticSelection,
} from '@/lib/telegram'

export type MotionPressVariant =
  | 'primary'
  | 'ghost'
  | 'icon'
  | 'subtle'
  | 'danger'

export type MotionPressHaptic =
  | 'light'
  | 'medium'
  | 'heavy'
  | 'selection'
  | null

type ButtonAttrs = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  | 'ref'
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

export interface MotionPressProps extends ButtonAttrs {
  variant?: MotionPressVariant
  haptic?: MotionPressHaptic
  ariaLabel?: string
  children?: ReactNode
}

const VARIANT_CLASS: Record<MotionPressVariant, string> = {
  primary: 'mp-press mp-press--primary',
  ghost: 'mp-press mp-press--ghost',
  icon: 'mp-press mp-press--icon',
  subtle: 'mp-press mp-press--subtle',
  danger: 'mp-press mp-press--danger',
}

export const MotionPress = forwardRef<
  HTMLButtonElement,
  MotionPressProps
>(function MotionPress(
  {
    variant = 'ghost',
    haptic: hapticKind = 'light',
    ariaLabel,
    className,
    onClick,
    type,
    children,
    disabled,
    ...rest
  },
  ref,
) {
  const reduce = useReducedMotion()
  const klass = [VARIANT_CLASS[variant], className]
    .filter(Boolean)
    .join(' ')

  const handleClick: React.MouseEventHandler<
    HTMLButtonElement
  > = (e) => {
    if (disabled) return
    try {
      if (hapticKind === 'selection') {
        hapticSelection()
      } else if (hapticKind) {
        haptic(hapticKind)
      }
    } catch {
      /* ignore */
    }
    onClick?.(e)
  }

  return (
    <m.button
      ref={ref}
      type={type ?? 'button'}
      className={klass}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={handleClick}
      whileTap={
        reduce || disabled
          ? undefined
          : { scale: 0.92 }
      }
      whileHover={
        reduce || disabled
          ? undefined
          : { scale: 1.02 }
      }
      transition={reduce ? TWEEN_FAST : SPRING_PRESS}
      {...rest}
    >
      {children}
    </m.button>
  )
})
