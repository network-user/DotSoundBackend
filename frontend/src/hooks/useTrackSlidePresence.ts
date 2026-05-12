import { useMemo } from 'react'
import type { Transition } from 'framer-motion'
import {
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { usePlayerMeta } from '@/store/PlayerContext'

const SLIDE_PX = 56

const SPRING_SLIDE: Transition = {
  type: 'spring',
  stiffness: 380,
  damping: 28,
  mass: 0.8,
}

export type TrackChangeSlide = {
  bump: number
  dir: 0 | 1 | -1
}

type SlideFrame = {
  x?: number
  opacity: number
  scale?: number
}

export function trackSlidePresenceProps(
  dir: 0 | 1 | -1,
  reduce: boolean,
): {
  initial: SlideFrame
  animate: SlideFrame
  exit: SlideFrame
  transition: Transition
} {
  if (reduce) {
    return {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
      exit: { opacity: 0 },
      transition: TWEEN_FAST,
    }
  }
  if (dir === 0) {
    return {
      initial: { opacity: 0, scale: 0.92 },
      animate: { opacity: 1, scale: 1 },
      exit: { opacity: 0, scale: 0.92 },
      transition: SPRING_SLIDE,
    }
  }
  return {
    initial: { x: dir * SLIDE_PX, opacity: 0 },
    animate: { x: 0, opacity: 1 },
    exit: { x: -dir * SLIDE_PX, opacity: 0 },
    transition: SPRING_SLIDE,
  }
}

export function useTrackSlidePresence() {
  const { trackChangeSlide } = usePlayerMeta()
  const reduceMotion = useReducedMotion()
  const reduce = Boolean(reduceMotion)
  return useMemo(
    () =>
      trackSlidePresenceProps(
        trackChangeSlide.dir,
        reduce,
      ),
    [
      trackChangeSlide.bump,
      trackChangeSlide.dir,
      reduce,
    ],
  )
}
