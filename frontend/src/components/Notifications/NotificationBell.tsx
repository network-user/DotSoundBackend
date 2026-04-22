import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { onWS } from '@/lib/ws'
import { Icon } from '@/components/Icon/Icon'
import { NotificationList } from '@/components/Notifications/NotificationList'

export function NotificationBell() {
  const [count, setCount] = useState(0)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    api
      .getUnreadCount()
      .then((r) => setCount(r.count))
      .catch(() => {})
    const off = onWS('notification', () => {
      setCount((p) => p + 1)
    })
    return off
  }, [])

  const handleOpen = () => {
    const next = !open
    setOpen(next)
    if (next && count > 0) {
      api
        .markAllNotificationsRead()
        .then(() => setCount(0))
        .catch(() => {})
    }
  }

  return (
    <div className="notification-bell-wrapper">
      <button
        className="notification-bell-btn"
        onClick={handleOpen}
        aria-label={
          count > 0
            ? `Уведомления (${count})`
            : 'Уведомления'
        }
      >
        <Icon name="bell" size={20} />
        {count > 0 && (
          <span className="notification-badge pulse">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      <NotificationList
        open={open}
        onClose={() => setOpen(false)}
      />
    </div>
  )
}
