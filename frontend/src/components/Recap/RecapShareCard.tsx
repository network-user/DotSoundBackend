import { MotionPress } from '@/components/ui/MotionPress'
import { m, useReducedMotion } from '@/lib/motion'

export interface RecapShareCardProps {
  brandLabel: string
  totalMinutes: number
  headline: string
  minutesCaption: string
  collageSrc: readonly string[]
  saveLabel: string
  shareLabel: string
  exportTodoHint: string
  onSave: () => void
  onShare: () => void
}

export function RecapShareCard({
  brandLabel,
  totalMinutes,
  headline,
  minutesCaption,
  collageSrc,
  saveLabel,
  shareLabel,
  exportTodoHint,
  onSave,
  onShare,
}: RecapShareCardProps) {
  const reduce = useReducedMotion()
  const tiles = collageSrc.slice(0, 4)
  return (
    <div className="rh-share-card">
      <div className="rh-share-card__inner">
        <div className="rh-share-collage">
          {tiles.map((src, i) => (
            <div
              key={i}
              className="rh-share-collage__cell"
            >
              <img src={src} alt="" decoding="async" />
            </div>
          ))}
        </div>
        <p className="rh-share-eyebrow">{headline}</p>
        <m.p
          className="rh-share-big"
          initial={false}
          animate={
            reduce
              ? { scale: 1 }
              : { scale: [1, 1.03, 1] }
          }
          transition={{
            duration: 2.4,
            repeat: reduce ? 0 : Infinity,
            ease: 'easeInOut',
          }}
        >
          {totalMinutes.toLocaleString()}
        </m.p>
        <p className="rh-share-unit">{minutesCaption}</p>
        <div className="rh-share-watermark" aria-hidden="true">
          {brandLabel}
        </div>
      </div>
      <p className="rh-share-todo">{exportTodoHint}</p>
      <div className="rh-share-actions">
        <MotionPress
          type="button"
          variant="ghost"
          className="rh-share-action"
          onClick={onSave}
        >
          {saveLabel}
        </MotionPress>
        <MotionPress
          type="button"
          variant="primary"
          className="rh-share-action"
          onClick={onShare}
        >
          {shareLabel}
        </MotionPress>
      </div>
    </div>
  )
}
