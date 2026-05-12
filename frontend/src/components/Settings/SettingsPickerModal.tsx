import { useEffect } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

export interface PickerOption {
  value: string
  label: string
  sublabel?: string
}

interface Props {
  open: boolean
  onClose: () => void
  title: string
  description: string
  options: PickerOption[]
  value: string
  onChange: (value: string) => void
  optionLayout?: 'inline' | 'stacked'
}

export function SettingsPickerModal({
  open,
  onClose,
  title,
  description,
  options,
  value,
  onChange,
  optionLayout = 'inline',
}: Props) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="spmodal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="spmodal">
        <div className="spmodal__header">
          <span className="spmodal__title">{title}</span>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn spmodal__close"
            ariaLabel="Закрыть"
            onClick={onClose}
          >
            <Icon name="x" size={18} />
          </MotionPress>
        </div>
        <p className="spmodal__desc">{description}</p>
        <div className="spmodal__options">
          {options.map((opt) => (
            <MotionPress
              key={opt.value}
              type="button"
              variant="ghost"
              haptic="selection"
              className={`spmodal__pill${value === opt.value ? ' spmodal__pill--active' : ''}${optionLayout === 'stacked' ? ' spmodal__pill--stacked' : ''}`}
              onClick={() => {
                onChange(opt.value)
                onClose()
              }}
            >
              <div className="spmodal__pill-inner">
                {optionLayout === 'stacked' ? (
                  <>
                    <div className="spmodal__pill-text">
                      <span className="spmodal__pill-label">
                        {opt.label}
                      </span>
                      {opt.sublabel && (
                        <span className="spmodal__pill-sub">
                          {opt.sublabel}
                        </span>
                      )}
                    </div>
                    {value === opt.value && (
                      <Icon
                        name="check"
                        size={14}
                        className="spmodal__pill-check"
                      />
                    )}
                  </>
                ) : (
                  <>
                    <span className="spmodal__pill-label">
                      {opt.label}
                    </span>
                    {opt.sublabel && (
                      <span className="spmodal__pill-sub">
                        {opt.sublabel}
                      </span>
                    )}
                    {value === opt.value && (
                      <Icon
                        name="check"
                        size={14}
                        className="spmodal__pill-check"
                      />
                    )}
                  </>
                )}
              </div>
            </MotionPress>
          ))}
        </div>
      </div>
    </div>
  )
}
