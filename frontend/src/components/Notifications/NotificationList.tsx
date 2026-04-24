import {
  useEffect,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { onWS } from '@/lib/ws'
import { Icon } from '@/components/Icon/Icon'
import { useExitTransition } from '@/hooks/useExitTransition'
import {
  resolveNotificationText,
} from '@/lib/notificationText'
import type { AppNotification } from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
  onMutate?: () => void
}

const KIND_ICON: Record<string, string> = {
  import_completed: 'download',
  import_failed: 'alert-triangle',
  account_warning: 'alert-triangle',
  account_banned: 'shield',
  account_restored: 'check',
  complaint_resolved: 'check',
  complaint_dismissed: 'info',
  complaint_in_progress: 'clock',
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

function fmtDate(
  iso: string,
  t: (k: string, o?: { count: number }) => string,
  lng: string,
): string {
  try {
    const now = Date.now()
    const tms = new Date(iso).getTime()
    const diff = (now - tms) / 1000
    if (diff < 60) {
      return t('notifications.time.justNow')
    }
    if (diff < 3600) {
      return t('notifications.time.minutes', {
        count: Math.floor(diff / 60),
      })
    }
    if (diff < 86400) {
      return t('notifications.time.hours', {
        count: Math.floor(diff / 3600),
      })
    }
    return new Date(iso).toLocaleDateString(
      lng?.startsWith('ru') ? 'ru-RU' : 'en-US',
      { day: '2-digit', month: 'short' },
    )
  } catch {
    return iso
  }
}

export function NotificationList({
  open,
  onClose,
  onMutate,
}: Props) {
  const { t, i18n } = useTranslation()
  const exit = useExitTransition(open)
  const [items, setItems] = useState<
    AppNotification[]
  >([])
  const [loading, setLoading] = useState(true)
  const [menuOpenId, setMenuOpenId] = useState<
    number | null
  >(null)

  useEffect(() => {
    if (menuOpenId == null) return
    const onDoc = (e: MouseEvent) => {
      if (menuOpenId == null) return
      const w = (e.target as Element | null)?.closest(
        '[data-notif-id]',
      )
      if (
        w &&
        Number(
          w.getAttribute('data-notif-id'),
        ) === menuOpenId
      ) {
        return
      }
      setMenuOpenId(null)
    }
    document.addEventListener('mousedown', onDoc)
    return () =>
      document.removeEventListener(
        'mousedown',
        onDoc,
      )
  }, [menuOpenId])

  const refresh = () => {
    api
      .getNotifications()
      .then((res) => setItems(res || []))
      .catch(() => setItems([]))
  }

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
      refresh()
    })
    return off
  }, [open])

  const handleMarkRead = async (id: number) => {
    setItems((prev) =>
      prev.map((n) =>
        n.id === id
          ? { ...n, is_read: true }
          : n,
      ),
    )
    try {
      await api.markNotificationRead(id)
      onMutate?.()
    } catch {
      /* noop */
    }
  }

  const handleRowClick = (id: number) => {
    setMenuOpenId(null)
    void handleMarkRead(id)
  }

  const handleMarkUnread = async (id: number) => {
    setMenuOpenId(null)
    setItems((prev) =>
      prev.map((n) =>
        n.id === id
          ? { ...n, is_read: false }
          : n,
      ),
    )
    try {
      await api.markNotificationUnread(id)
      onMutate?.()
    } catch {
      /* noop */
    }
  }

  const handleDelete = async (id: number) => {
    setMenuOpenId(null)
    setItems((prev) => prev.filter((n) => n.id !== id))
    try {
      await api.deleteNotification(id)
      onMutate?.()
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
          <h3>
            {t('notifications.title')}
          </h3>
          <button
            onClick={onClose}
            aria-label={t(
              'notifications.closeAria',
            )}
          >
            <Icon name="x" size={18} />
          </button>
        </div>
        {loading ? (
          <div className="notification-skeleton">
            {Array.from({ length: 4 }).map(
              (_, i) => (
                <div
                  key={i}
                  className="skeleton-notification shimmer"
                />
              ),
            )}
          </div>
        ) : items.length === 0 ? (
          <div className="notification-empty">
            <Icon
              name="bell"
              size={28}
              className="notification-empty-icon"
            />
            <div className="notification-empty-title">
              {t('notifications.emptyTitle')}
            </div>
            <div className="notification-empty-hint">
              {t('notifications.emptyHint')}
            </div>
          </div>
        ) : (
          <div className="notification-items">
            {items.map((n) => {
              const { title, body } =
                resolveNotificationText(
                  n,
                  t,
                )
              return (
                <div
                  key={n.id}
                  className="notification-item-row"
                  data-notif-id={n.id}
                >
                  <button
                    type="button"
                    className={`notification-item${
                      n.is_read
                        ? ''
                        : ' unread'
                    }`}
                    onClick={() =>
                      handleRowClick(n.id)
                    }
                  >
                    <span className="notification-icon">
                      <Icon
                        name={iconFor(
                          n.type,
                        )}
                        size={16}
                      />
                    </span>
                    <span className="notification-content">
                      <span
                        className="notification-title"
                      >
                        {title}
                      </span>
                      <span
                        className="notification-body"
                      >
                        {body}
                      </span>
                    </span>
                    <span
                      className="notification-time"
                    >
                      {fmtDate(
                        n.created_at,
                        t,
                        i18n.language,
                      )}
                    </span>
                  </button>
                  <div className="notification-item-menu">
                    <button
                      type="button"
                      className="notification-more"
                      onClick={(e) => {
                        e.stopPropagation()
                        setMenuOpenId(
                          menuOpenId ===
                            n.id
                            ? null
                            : n.id,
                        )
                      }}
                      aria-label={t(
                        'notifications.moreActions',
                      )}
                      aria-expanded={
                        menuOpenId === n.id
                      }
                    >
                      <Icon
                        name="more-vertical"
                        size={16}
                      />
                    </button>
                    {menuOpenId ===
                      n.id && (
                      <ul
                        className="notification-menu-dropdown"
                        role="menu"
                      >
                        <li role="none">
                          <button
                            type="button"
                            role="menuitem"
                            className="notification-menu-item"
                            onClick={(
                              e,
                            ) => {
                              e.stopPropagation()
                              setMenuOpenId(
                                null,
                              )
                              void handleMarkRead(
                                n.id,
                              )
                            }}
                            disabled={n.is_read}
                          >
                            {t(
                              'notifications.markRead',
                            )}
                          </button>
                        </li>
                        <li role="none">
                          <button
                            type="button"
                            role="menuitem"
                            className="notification-menu-item"
                            onClick={(
                              e,
                            ) => {
                              e.stopPropagation()
                              void handleMarkUnread(
                                n.id,
                              )
                            }}
                            disabled={!n.is_read}
                          >
                            {t(
                              'notifications.markUnread',
                            )}
                          </button>
                        </li>
                        <li role="none">
                          <button
                            type="button"
                            role="menuitem"
                            className="notification-menu-item danger"
                            onClick={(
                              e,
                            ) => {
                              e.stopPropagation()
                              void handleDelete(
                                n.id,
                              )
                            }}
                          >
                            {t(
                              'notifications.delete',
                            )}
                          </button>
                        </li>
                      </ul>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
