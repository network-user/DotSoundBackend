import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import type { AppNotification } from '@/types/api'

interface Props {
  onClose: () => void
}

export function NotificationList({ onClose }: Props) {
  const [items, setItems] = useState<AppNotification[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getNotifications().then(setItems).finally(() => setLoading(false))
  }, [])

  return (
    <div className="notification-overlay" onClick={onClose}>
      <div className="notification-panel slide-in" onClick={(e) => e.stopPropagation()}>
        <div className="notification-header">
          <h3>Уведомления</h3>
          <button onClick={onClose}><Icon name="x" size={18} /></button>
        </div>
        {loading ? (
          <div className="notification-skeleton">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton-notification shimmer" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">Нет уведомлений</div>
        ) : (
          <div className="notification-items">
            {items.map((n) => (
              <div
                key={n.id}
                className={`notification-item fade-in ${n.is_read ? '' : 'unread'}`}
              >
                <div className="notification-content">
                  <span className="notification-title">{n.title}</span>
                  <span className="notification-body">{n.body}</span>
                </div>
                <span className="notification-time">
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
