import { LayoutGroup } from 'framer-motion'
import { m, SPRING_LAYOUT } from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'

export interface RangeOption<V extends string | number> {
  value: V
  label: string
}

interface Props<V extends string | number> {
  options: RangeOption<V>[]
  value: V
  onChange: (next: V) => void
  groupId?: string
  ariaLabel?: string
  className?: string
}

export function AdminRangeSwitch<V extends string | number>({
  options,
  value,
  onChange,
  groupId = 'admin-range-switch',
  ariaLabel,
  className,
}: Props<V>) {
  const klass = ['admin-range-switch', 'adm-r-range', className]
    .filter(Boolean)
    .join(' ')
  return (
    <LayoutGroup id={groupId}>
      <div
        className={klass}
        role="tablist"
        aria-label={ariaLabel}
      >
        {options.map((opt) => {
          const active = opt.value === value
          return (
            <MotionPress
              key={String(opt.value)}
              type="button"
              variant="ghost"
              haptic="selection"
              role="tab"
              aria-selected={active}
              className={
                active
                  ? 'admin-range-switch__btn adm-r-range__btn is-active'
                  : 'admin-range-switch__btn adm-r-range__btn'
              }
              onClick={() => {
                if (!active) onChange(opt.value)
              }}
            >
              {active && (
                <m.span
                  layoutId={`${groupId}-indicator`}
                  className="adm-r-range__indicator"
                  transition={SPRING_LAYOUT}
                />
              )}
              <span className="adm-r-range__label">{opt.label}</span>
            </MotionPress>
          )
        })}
      </div>
    </LayoutGroup>
  )
}
