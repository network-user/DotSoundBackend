import { useEffect, type MouseEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  hint: ReactNode
  confirmLabel: string
  cancelLabel: string
  busy?: boolean
  onConfirm: () => void
}

export function SettingsConfirmModal({
  open,
  onClose,
  title,
  hint,
  confirmLabel,
  cancelLabel,
  busy = false,
  onConfirm,
}: Props) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, busy, onClose])

  const handleBackdrop = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !busy) onClose()
  }

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div
      className="settings-confirm-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-confirm-title"
      onClick={handleBackdrop}
    >
      <div
        className="settings-confirm-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="settings-confirm-panel__header">
          <h3 id="settings-confirm-title">{title}</h3>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn"
            ariaLabel={cancelLabel}
            onClick={onClose}
            disabled={busy}
          >
            <Icon name="x" size={18} />
          </MotionPress>
        </div>
        <p className="settings-confirm-panel__hint">{hint}</p>
        <div className="settings-confirm-panel__actions">
          <MotionPress
            type="button"
            variant="primary"
            haptic="medium"
            className="btn-primary"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? '…' : confirmLabel}
          </MotionPress>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="btn-secondary"
            disabled={busy}
            onClick={onClose}
          >
            {cancelLabel}
          </MotionPress>
        </div>
      </div>
    </div>,
    document.body,
  )
}
