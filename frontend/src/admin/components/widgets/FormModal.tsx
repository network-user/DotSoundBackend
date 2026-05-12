import { ReactNode, useEffect, useRef } from 'react'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  open: boolean
  title: ReactNode
  subtitle?: ReactNode
  onClose: () => void
  onSubmit?: () => void | Promise<void>
  submitText?: string
  cancelText?: string
  submitting?: boolean
  submitDisabled?: boolean
  danger?: boolean
  error?: string | null
  size?: 'sm' | 'md' | 'lg'
  closeOnOverlayClick?: boolean
  children: ReactNode
  footer?: ReactNode
}

const focusableSelector =
  'a[href], button:not([disabled]), textarea:not([disabled]), ' +
  'input:not([disabled]):not([type="hidden"]), ' +
  'select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function FormModal({
  open,
  title,
  subtitle,
  onClose,
  onSubmit,
  submitText = 'Save',
  cancelText = 'Cancel',
  submitting = false,
  submitDisabled = false,
  danger = false,
  error,
  size = 'md',
  closeOnOverlayClick = true,
  children,
  footer,
}: Props) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const lastFocus = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    lastFocus.current = document.activeElement as HTMLElement | null
    const node = dialogRef.current
    if (node) {
      const first = node.querySelector<HTMLElement>(focusableSelector)
      first?.focus()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) {
        e.stopPropagation()
        onClose()
        return
      }
      if (e.key === 'Tab' && node) {
        const focusables = Array.from(
          node.querySelectorAll<HTMLElement>(focusableSelector),
        ).filter((el) => !el.hasAttribute('aria-hidden'))
        if (focusables.length === 0) return
        const idx = focusables.indexOf(
          document.activeElement as HTMLElement,
        )
        if (e.shiftKey && (idx <= 0)) {
          e.preventDefault()
          focusables[focusables.length - 1].focus()
        } else if (!e.shiftKey && idx === focusables.length - 1) {
          e.preventDefault()
          focusables[0].focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      lastFocus.current?.focus?.()
    }
  }, [open, onClose, submitting])

  if (!open) return null

  const handleSubmit = async () => {
    if (!onSubmit || submitting || submitDisabled) return
    await onSubmit()
  }

  const handleOverlay = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!closeOnOverlayClick) return
    if (submitting) return
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className="admin-modal-overlay admin-form-modal-overlay"
      onClick={handleOverlay}
    >
      <div
        ref={dialogRef}
        className={`admin-modal admin-form-modal admin-form-modal--${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
      >
        <header className="admin-form-modal__head">
          <div className="admin-form-modal__title-block">
            <h3 className="admin-form-modal__title">{title}</h3>
            {subtitle ? (
              <p className="admin-form-modal__subtitle">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            className="admin-form-modal__close"
            aria-label="Close"
            onClick={() => !submitting && onClose()}
          >
            <Icon name="x" size={14} />
          </button>
        </header>

        <div className="admin-form-modal__body">{children}</div>

        {error ? (
          <div className="admin-form-modal__error" role="alert">
            <Icon name="alert-triangle" size={14} />
            <span>{error}</span>
          </div>
        ) : null}

        <footer className="admin-form-modal__foot">
          {footer ?? (
            <>
              <MotionPress
                variant="ghost"
                disabled={submitting}
                onClick={onClose}
              >
                {cancelText}
              </MotionPress>
              {onSubmit ? (
                <MotionPress
                  variant="primary"
                  disabled={submitting || submitDisabled}
                  onClick={handleSubmit}
                  className={
                    danger ? 'admin-prompt__btn--danger' : undefined
                  }
                >
                  {submitting ? '…' : submitText}
                </MotionPress>
              ) : null}
            </>
          )}
        </footer>
      </div>
    </div>
  )
}
