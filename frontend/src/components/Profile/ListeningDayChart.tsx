import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useMatchMedia } from '@/hooks/useMatchMedia'

export interface ListeningDayBucket {
  date: string
  minutes: number
}

function formatListeningMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} мин`
  const h = Math.floor(minutes / 60)
  const m = minutes - h * 60
  return m > 0 ? `${h} ч ${m} мин` : `${h} ч`
}

function formatChartDayLabel(dateIso: string, locale: string): string {
  const d = new Date(`${dateIso}T12:00:00`)
  if (Number.isNaN(d.getTime())) return dateIso
  return d.toLocaleDateString(locale, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

type ListeningDayChartProps = {
  buckets: ListeningDayBucket[]
}

export function ListeningDayChart({ buckets }: ListeningDayChartProps) {
  const { t, i18n } = useTranslation()
  const coarse = useMatchMedia('(pointer: coarse)')
  const [hoverDate, setHoverDate] = useState<string | null>(null)
  const [lockedDate, setLockedDate] = useState<string | null>(null)
  const chartRef = useRef<HTMLDivElement>(null)

  const max = Math.max(1, ...buckets.map((b) => b.minutes))

  useEffect(() => {
    setHoverDate(null)
    setLockedDate(null)
  }, [buckets])

  useEffect(() => {
    if (!coarse || !lockedDate) return
    const close = (ev: PointerEvent) => {
      const root = chartRef.current
      if (!root?.contains(ev.target as Node)) {
        setLockedDate(null)
      }
    }
    document.addEventListener('pointerdown', close, true)
    return () => document.removeEventListener('pointerdown', close, true)
  }, [coarse, lockedDate])

  const activeDate = coarse ? lockedDate : hoverDate
  const activeBucket = activeDate
    ? buckets.find((b) => b.date === activeDate)
    : null

  const handleChartPointerLeave = () => {
    if (!coarse) setHoverDate(null)
  }

  return (
    <div className="listening-day-chart">
      <div
        ref={chartRef}
        className="my-top-hours__chart"
        onPointerLeave={handleChartPointerLeave}
        role="list"
        aria-label={t('myTop.hoursByDay', 'Minutes by day')}
      >
        {buckets.map((b) => {
          const pct = Math.round((b.minutes / max) * 100)
          const isActive = b.date === activeDate
          const isDimmed =
            activeDate != null && b.date !== activeDate
          const dayLabel = formatChartDayLabel(b.date, i18n.language)
          const minsLabel = formatListeningMinutes(b.minutes)
          return (
            <div
              key={b.date}
              role="listitem"
              className={`my-top-hours__bar-wrap${isActive ? ' is-active' : ''}${
                isDimmed ? ' is-dimmed' : ''
              }`}
            >
              <button
                type="button"
                className="my-top-hours__bar-hit"
                tabIndex={0}
                aria-pressed={coarse ? lockedDate === b.date : undefined}
                aria-label={t('myTop.dayBarA11y', '{{day}}: {{mins}}', {
                  day: dayLabel,
                  mins: minsLabel,
                })}
                onPointerEnter={() => {
                  if (!coarse) setHoverDate(b.date)
                }}
                onPointerDown={(ev) => {
                  if (!coarse) return
                  ev.preventDefault()
                  setLockedDate((cur) =>
                    cur === b.date ? null : b.date,
                  )
                }}
                onFocus={() => {
                  if (!coarse) setHoverDate(b.date)
                }}
                onBlur={(ev) => {
                  if (coarse) return
                  const next = ev.relatedTarget as Node | null
                  if (!chartRef.current?.contains(next)) {
                    setHoverDate(null)
                  }
                }}
              >
                <span
                  className="my-top-hours__bar"
                  style={
                    {
                      '--bar-scale': `${Math.max(2, pct) / 100}`,
                    } as CSSProperties
                  }
                />
              </button>
            </div>
          )
        })}
      </div>
      <div className="listening-day-chart__detail" aria-live="polite">
        {activeBucket ? (
          <span className="listening-day-chart__detail--value">
            {formatChartDayLabel(activeBucket.date, i18n.language)}
            {' · '}
            {formatListeningMinutes(activeBucket.minutes)}
          </span>
        ) : (
          <span className="listening-day-chart__detail--muted">
            {coarse
              ? t('myTop.dayChartTapHint', 'Tap a bar for details')
              : t(
                  'myTop.dayChartHoverHint',
                  'Hover a bar for details',
                )}
          </span>
        )}
      </div>
    </div>
  )
}
