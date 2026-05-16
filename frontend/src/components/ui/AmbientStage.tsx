import {
  type ReactNode,
  useEffect,
  useState,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import {
  m,
  TWEEN_SLOW,
  useReducedMotion,
} from '@/lib/motion'
import {
  type CoverPalette,
  extractCoverPalette,
} from '@/lib/coverPalette'
import { isPerfLiteActive } from '@/lib/glassPerformance'

export interface AmbientStageProps {
  coverUrl?: string | null
  className?: string
  children?: ReactNode
}

const FALLBACK_TONES: [string, string, string] = [
  '#1c1c1c',
  '#2a2a2a',
  '#0d0d0d',
]

export function AmbientStage({
  coverUrl,
  className,
  children,
}: AmbientStageProps) {
  const reduce = useReducedMotion()
  const perfLite = isPerfLiteActive()
  const [palette, setPalette] = useState<CoverPalette | null>(null)
  const [paletteKey, setPaletteKey] = useState<string>('fallback')

  useEffect(() => {
    let cancelled = false
    if (!coverUrl || perfLite) {
      setPalette(null)
      setPaletteKey('fallback')
      return
    }
    extractCoverPalette(coverUrl)
      .then((p) => {
        if (cancelled) return
        setPalette(p)
        setPaletteKey(p ? coverUrl : 'fallback')
      })
      .catch(() => {
        if (cancelled) return
        setPalette(null)
        setPaletteKey('fallback')
      })
    return () => {
      cancelled = true
    }
  }, [coverUrl, perfLite])

  const tones = palette?.tones ?? FALLBACK_TONES

  return (
    <div
      className={['ambient-stage', className]
        .filter(Boolean)
        .join(' ')}
    >
      <AnimatePresence>
        <m.div
          key={paletteKey}
          className="ambient-stage__layers"
          initial={reduce ? { opacity: 1 } : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0 }}
          transition={reduce ? { duration: 0 } : TWEEN_SLOW}
          aria-hidden="true"
        >
          <div
            className="ambient-layer ambient-layer--a"
            style={{
              background: `radial-gradient(60% 60% at 25% 30%, ${tones[0]} 0%, transparent 60%)`,
            }}
          />
          <div
            className="ambient-layer ambient-layer--b"
            style={{
              background: `radial-gradient(55% 55% at 75% 35%, ${tones[1]} 0%, transparent 65%)`,
            }}
          />
          <div
            className="ambient-layer ambient-layer--c"
            style={{
              background: `radial-gradient(70% 70% at 50% 80%, ${tones[2]} 0%, transparent 70%)`,
            }}
          />
        </m.div>
      </AnimatePresence>
      <div className="ambient-stage__content">
        {children}
      </div>
    </div>
  )
}
