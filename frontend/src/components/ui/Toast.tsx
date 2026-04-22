import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { Icon } from '@/components/Icon/Icon'

type ToastKind = 'info' | 'success' | 'warning' | 'error'

interface ToastOpts {
  duration?: number
  action?: { label: string; onClick: () => void }
}

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
  duration: number
  leaving: boolean
  action?: { label: string; onClick: () => void }
}

interface ToastApi {
  show: (
    msg: string,
    kind?: ToastKind,
    opts?: ToastOpts,
  ) => number
  info: (msg: string, opts?: ToastOpts) => number
  success: (msg: string, opts?: ToastOpts) => number
  warning: (msg: string, opts?: ToastOpts) => number
  error: (msg: string, opts?: ToastOpts) => number
  dismiss: (id: number) => void
}

const ToastCtx = createContext<ToastApi | null>(null)

export function useToast(): ToastApi {
  const ctx = useContext(ToastCtx)
  if (!ctx) {
    return {
      show: () => -1,
      info: () => -1,
      success: () => -1,
      warning: () => -1,
      error: () => -1,
      dismiss: () => undefined,
    }
  }
  return ctx
}

export function ToastProvider({
  children,
}: {
  children: ReactNode
}) {
  const [items, setItems] = useState<ToastItem[]>([])
  const idRef = useRef(0)
  const timersRef = useRef<Map<number, number>>(new Map())

  const dismiss = useCallback((id: number) => {
    setItems((prev) =>
      prev.map((t) =>
        t.id === id ? { ...t, leaving: true } : t,
      ),
    )
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id))
      timersRef.current.delete(id)
    }, 220)
  }, [])

  const show = useCallback(
    (
      message: string,
      kind: ToastKind = 'info',
      opts?: ToastOpts,
    ) => {
      idRef.current += 1
      const id = idRef.current
      const duration = opts?.duration ?? 4500
      setItems((prev) => [
        ...prev.slice(-3),
        {
          id,
          kind,
          message,
          duration,
          leaving: false,
          action: opts?.action,
        },
      ])
      const handle = window.setTimeout(
        () => dismiss(id),
        duration,
      )
      timersRef.current.set(id, handle)
      return id
    },
    [dismiss],
  )

  useEffect(() => {
    const map = timersRef.current
    return () => {
      map.forEach((h) => window.clearTimeout(h))
      map.clear()
    }
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      show,
      info: (msg, opts) => show(msg, 'info', opts),
      success: (msg, opts) =>
        show(msg, 'success', opts),
      warning: (msg, opts) =>
        show(msg, 'warning', opts),
      error: (msg, opts) => show(msg, 'error', opts),
      dismiss,
    }),
    [show, dismiss],
  )

  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div
        className="toast-host"
        aria-live="polite"
        aria-atomic="false"
      >
        {items.map((t) => (
          <ToastView
            key={t.id}
            item={t}
            onClose={() => dismiss(t.id)}
          />
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

const iconForKind: Record<ToastKind, string> = {
  info: 'info',
  success: 'check',
  warning: 'alert-triangle',
  error: 'alert-triangle',
}

function ToastView({
  item,
  onClose,
}: {
  item: ToastItem
  onClose: () => void
}) {
  const cls = [
    'toast',
    `toast--${item.kind}`,
    item.leaving ? 'is-leaving' : '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <div className={cls} role="status">
      <span className="toast__icon" aria-hidden="true">
        <Icon
          name={iconForKind[item.kind]}
          size={18}
        />
      </span>
      <span className="toast__msg">{item.message}</span>
      {item.action && (
        <button
          type="button"
          className="toast__close"
          onClick={() => {
            item.action?.onClick()
            onClose()
          }}
        >
          {item.action.label}
        </button>
      )}
      <button
        type="button"
        className="toast__close"
        aria-label="Закрыть"
        onClick={onClose}
      >
        <Icon name="x" size={16} />
      </button>
    </div>
  )
}
