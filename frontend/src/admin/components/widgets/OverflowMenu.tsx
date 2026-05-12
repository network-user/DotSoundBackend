import {
  ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'

export interface OverflowItem {
  id: string
  label: ReactNode
  hint?: ReactNode
  icon?: string
  disabled?: boolean
  danger?: boolean
  onSelect: () => void
}

interface Props {
  items: OverflowItem[]
  label?: string
  buttonLabel?: ReactNode
  align?: 'left' | 'right'
}

export function OverflowMenu({
  items,
  label = 'More actions',
  buttonLabel,
  align = 'right',
}: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!rootRef.current) return
      if (!rootRef.current.contains(e.target as Node)) close()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        close()
      }
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, close])

  if (items.length === 0) return null

  return (
    <div
      ref={rootRef}
      className={
        align === 'left'
          ? 'admin-overflow admin-overflow--left'
          : 'admin-overflow'
      }
    >
      <MotionPress
        type="button"
        variant="ghost"
        haptic="selection"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        className="admin-overflow__btn"
      >
        {buttonLabel ?? (
          <>
            <Icon name="more-horizontal" size={16} />
            <span className="admin-overflow__btn-text">More</span>
          </>
        )}
      </MotionPress>
      {open ? (
        <div className="admin-overflow__menu" role="menu">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              className={
                item.danger
                  ? 'admin-overflow__item admin-overflow__item--danger'
                  : 'admin-overflow__item'
              }
              disabled={item.disabled}
              onClick={() => {
                if (item.disabled) return
                close()
                item.onSelect()
              }}
            >
              {item.icon ? (
                <Icon
                  name={item.icon}
                  size={14}
                  className="admin-overflow__item-icon"
                />
              ) : (
                <span
                  className="admin-overflow__item-icon"
                  aria-hidden
                />
              )}
              <span className="admin-overflow__item-label">
                {item.label}
              </span>
              {item.hint ? (
                <span className="admin-overflow__item-hint">
                  {item.hint}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
