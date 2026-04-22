import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { onWS } from '@/lib/ws'
import { Icon } from '@/components/Icon/Icon'
import { useExitTransition } from '@/hooks/useExitTransition'
import type { AppNotification } from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
}

const KIND_ICON: Record<string, string> = {
  account_warning: 'alert-triangle',
  account_banned: 'shield',
  account_restored: 'check',
  complaint_resolved: 'check',
  complaint_dismissed: 'info',
  track_hidden: 'eye',
  track_restored: 'check',
  admin_message: 'shield',
  follow: 'user',
  like: 'heart',
  message: 'message-circle',
  comment: 'message-circle',
}

function iconFor(type: string): string {
  return KIND_ICON[type] || 'bell'
}

function fmtDate(iso: string): string {
  try {
    const now = Date.now()
    const t = new Date(iso).getTime()
    const diff = (now - t) / 1000
    if (diff < 60) return 'только что'
    if (diff < 3600)
      return `${Math.floor(diff / 60)} мин`
    if (diff < 86400)
      return `${Math.floor(diff / 3600)} ч`
    return new Date(iso).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: 'short',
    })
  } catch {
    return iso
  }
}

export function NotificationList({
  open,
  onClose,
}: Props) {
  const exit = useExitTransition(open)
  const [items, setItems] = useState<
    AppNotification[]
  >([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    api
      .getNotifications()
      .then((res) => {
        setItems(res || [])
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
    const off = onWS('notification', () => {
      api
        .getNotifications()
        .then((res) => setItems(res || []))
        .catch(() => {})
    })
    return off
  }, [open])

  const handleMark = async (id: number) => {
    setItems((prev) =>
      prev.map((n) =>
        n.id === id ? { ...n, is_read: true } : n,
      ),
    )
    try {
      await api.markNotificationRead(id)
    } catch {
      /* noop */
    }
  }

  if (!exit.mounted) return null

  return (
    <div
      className={`notification-overlay${exit.cls}`}
      onClick={onClose}
    >
      <div
        className={`notification-panel${exit.cls}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="notification-header">
          <h3>Уведомления</h3>
          <button onClick={onClose} aria-label="Закрыть">
            <Icon name="x" size={18} />
          </button>
        </div>
        {loading ? (
          <div className="notification-skeleton">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="skeleton-notification shimmer"
              />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="notification-empty">
            <Icon
              name="bell"
              size={28}
              className="notification-empty-icon"
            />
            <div className="notification-empty-title">
              Тут пока пусто
            </div>
            <div className="notification-empty-hint">
              Когда что-то случится — увидишь
              здесь.
            </div>
          </div>
        ) : (
          <div className="notification-items">
            {items.map((n) => (
              <button
                key={n.id}
                type="button"
                className={`notification-item${n.is_read ? '' : ' unread'}`}
                onClick={() => handleMark(n.id)}
              >
                <span className="notification-icon">
                  <Icon name={iconFor(n.type)} size={16} />
                </span>
                <span className="notification-content">
                  <span className="notification-title">
                    {n.title}
                  </span>
                  <span className="notification-body">
                    {n.body}
                  </span>
                </span>
                <span className="notification-time">
                  {fmtDate(n.created_at)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
