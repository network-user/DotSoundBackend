import {
  type Transition,
  type Variants,
  domAnimation,
  LazyMotion,
  m,
  useReducedMotion,
} from 'framer-motion'

export const SPRING_GENTLE: Transition = {
  type: 'spring',
  stiffness: 220,
  damping: 28,
  mass: 0.9,
}

export const SPRING_SNAPPY: Transition = {
  type: 'spring',
  stiffness: 420,
  damping: 32,
  mass: 0.7,
}

export const SPRING_BOUNCY: Transition = {
  type: 'spring',
  stiffness: 320,
  damping: 18,
  mass: 0.85,
}

export const SPRING_PRESS: Transition = {
  type: 'spring',
  stiffness: 520,
  damping: 20,
  mass: 0.5,
}

export const SPRING_LAYOUT: Transition = {
  type: 'spring',
  stiffness: 260,
  damping: 30,
}

export const TWEEN_FAST: Transition = {
  type: 'tween',
  duration: 0.16,
  ease: [0.22, 0.61, 0.36, 1],
}

export const TWEEN_SLOW: Transition = {
  type: 'tween',
  duration: 0.36,
  ease: [0.16, 1, 0.3, 1],
}

export const VARIANTS_FADE_UP: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: TWEEN_FAST },
}

export const VARIANTS_SCALE_IN: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: SPRING_GENTLE },
}

export const VARIANTS_PAGE_SLIDE: Variants = {
  hidden: { opacity: 0, x: 24 },
  visible: { opacity: 1, x: 0, transition: SPRING_GENTLE },
  exit: { opacity: 0, x: -16, transition: TWEEN_FAST },
}

export const VARIANTS_SHEET_SLIDE_UP: Variants = {
  hidden: { opacity: 0, y: '100%' },
  visible: { opacity: 1, y: 0, transition: SPRING_GENTLE },
  exit: { opacity: 0, y: '8%', transition: TWEEN_FAST },
}

export function shouldReduceMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return false
  }
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

export function withReduce<T>(motion: T, reducedFallback: T): T {
  return shouldReduceMotion() ? reducedFallback : motion
}

export { LazyMotion, domAnimation, m, useReducedMotion }
