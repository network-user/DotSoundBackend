import { AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { m, useReducedMotion } from '@/lib/motion'

type PlaybackModeIndicatorVariant =
  | 'mini'
  | 'now-playing'
  | 'track-card'
  | 'player-bar'

interface PlaybackModeIndicatorProps {
  shuffleOn: boolean
  variant?: PlaybackModeIndicatorVariant
  className?: string
}

type TranslationFn = ReturnType<typeof useTranslation>['t']

export function playbackModeLabel(
  shuffleOn: boolean,
  t: TranslationFn,
) {
  return shuffleOn
    ? t('redesign.player.modeShuffle')
    : t('redesign.player.modeSequential')
}

export function PlaybackModeIndicator({
  shuffleOn,
  variant = 'mini',
  className,
}: PlaybackModeIndicatorProps) {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const mode = shuffleOn ? 'shuffle' : 'sequential'
  const label = playbackModeLabel(shuffleOn, t)
  const ariaLabel = t('redesign.player.modeAria', {
    mode: label,
  })
  const classes = [
    'playback-mode-indicator',
    `playback-mode-indicator--${variant}`,
    `playback-mode-indicator--${mode}`,
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <span
      className={classes}
      title={ariaLabel}
      aria-label={ariaLabel}
    >
      <AnimatePresence initial={false} mode="wait">
        <m.span
          key={`${mode}-icon`}
          className="playback-mode-indicator__icon"
          initial={
            reduce
              ? { opacity: 0 }
              : {
                  opacity: 0,
                  scale: 0.72,
                  rotate: shuffleOn ? -28 : 18,
                }
          }
          animate={{ opacity: 1, scale: 1, rotate: 0 }}
          exit={
            reduce
              ? { opacity: 0 }
              : {
                  opacity: 0,
                  scale: 0.82,
                  rotate: shuffleOn ? 20 : -20,
                }
          }
          transition={
            reduce
              ? { duration: 0 }
              : {
                  type: 'spring',
                  stiffness: 520,
                  damping: 24,
                  mass: 0.55,
                }
          }
        >
          <Icon name={shuffleOn ? 'shuffle' : 'list'} size={13} />
        </m.span>
      </AnimatePresence>
      <AnimatePresence initial={false} mode="wait">
        <m.span
          key={mode}
          className="playback-mode-indicator__label"
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, y: -5 }}
          transition={
            reduce
              ? { duration: 0 }
              : {
                  duration: 0.18,
                  ease: [0.22, 0.61, 0.36, 1],
                }
          }
        >
          {label}
        </m.span>
      </AnimatePresence>
      <span className="playback-mode-indicator__pulse" aria-hidden />
    </span>
  )
}
