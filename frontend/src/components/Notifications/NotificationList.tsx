import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { onWS } from '@/lib/ws'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useExitTransition } from '@/hooks/useExitTransition'
import {
  resolveNotificationText,
} from '@/lib/notificationText'
import { usePlayerActions } from '@/store/PlayerContext'
import type { AppNotification } from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
  onMutate?: () => void
}

const NOTIF_MENU_W = 200
const NOTIF_MENU_EST_H = 148
const NOTIF_VIEW_PAD = 8

function computeMenuPos(
  anchor: HTMLElement,
): { top: number; left: number } {
  const r = anchor.getBoundingClientRect()
  const vh = window.innerHeight
  const vw = window.innerWidth
  const left = Math.max(
    NOTIF_VIEW_PAD,
    Math.min(
      r.right - NOTIF_MENU_W,
      vw - NOTIF_MENU_W - NOTIF_VIEW_PAD,
    ),
  )
  const downTop = r.bottom + 6
  const upTop = r.top - NOTIF_MENU_EST_H - 6
  let top: number
  if (downTop + NOTIF_MENU_EST_H <= vh - NOTIF_VIEW_PAD) {
    top = downTop
  } else if (upTop >= NOTIF_VIEW_PAD) {
    top = upTop
  } else {
    top = Math.max(
      NOTIF_VIEW_PAD,
      Math.min(
        downTop,
        vh - NOTIF_MENU_EST_H - NOTIF_VIEW_PAD,
      ),
    )
  }
  return { top, left }
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
  comment_like: 'heart',
  comment_reply: 'message-circle',
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
  const { openTrackAtComment } = usePlayerActions()
  const exit = useExitTransition(open)
  const [items, setItems] = useState<
    AppNotification[]
  >([])
  const [loading, setLoading] = useState(true)
  const [menuOpenId, setMenuOpenId] = useState<
    number | null
  >(null)
  const [menuPos, setMenuPos] = useState<{
    top: number
    left: number
  } | null>(null)

  const placeMenu = useCallback((id: number) => {
    const el = document.querySelector(
      `[data-notif-menu-anchor="${id}"]`,
    ) as HTMLElement | null
    if (!el) {
      return
    }
    setMenuPos(computeMenuPos(el))
  }, [])

  useLayoutEffect(() => {
    if (menuOpenId == null) {
      setMenuPos(null)
      return
    }
    placeMenu(menuOpenId)
  }, [menuOpenId, placeMenu, items])

  useEffect(() => {
    if (menuOpenId == null) return
    const onReposition = () => {
      placeMenu(menuOpenId)
    }
    window.addEventListener('resize', onReposition)
    window.addEventListener('scroll', onReposition, true)
    const itemsEl =
      document.querySelector('.notification-items')
    itemsEl?.addEventListener('scroll', onReposition, {
      passive: true,
    })
    return () => {
      window.removeEventListener('resize', onReposition)
      window.removeEventListener('scroll', onReposition, true)
      itemsEl?.removeEventListener(
        'scroll',
        onReposition,
      )
    }
  }, [menuOpenId, placeMenu])

  useEffect(() => {
    if (menuOpenId == null) return
    const onDoc = (e: MouseEvent) => {
      if (menuOpenId == null) return
      const t = e.target as Element | null
      if (t?.closest?.('.notification-menu-portal')) {
        return
      }
      const w = t?.closest?.(
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
      setMenuPos(null)
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
    if (!open) {
      setMenuOpenId(null)
      setMenuPos(null)
      return
    }
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

  const handleRowClick = async (n: AppNotification) => {
    setMenuOpenId(null)
    setMenuPos(null)
    void handleMarkRead(n.id)
    if (
      (n.type === 'comment_like' ||
        n.type === 'comment_reply') &&
      n.data &&
      typeof n.data === 'object'
    ) {
      const raw = n.data as Record<string, unknown>
      const tid = Number(raw.track_id)
      const cid = Number(raw.comment_id)
      if (
        Number.isFinite(tid) &&
        tid > 0 &&
        Number.isFinite(cid) &&
        cid > 0
      ) {
        onClose()
        try {
          const tr = await api.getTrack(tid)
          await openTrackAtComment(tr, cid)
        } catch {
          /* noop */
        }
      }
    }
  }

  const handleMarkUnread = async (id: number) => {
    setMenuOpenId(null)
    setMenuPos(null)
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
    setMenuPos(null)
    setItems((prev) => prev.filter((n) => n.id !== id))
    try {
      await api.deleteNotification(id)
      onMutate?.()
    } catch {
      /* noop */
    }
  }

  if (!exit.mounted) return null

  const menuN =
    menuOpenId == null
      ? null
      : items.find((x) => x.id === menuOpenId) ||
        null

  const menuPortal =
    menuOpenId != null &&
    menuPos &&
    menuN && (
      createPortal(
        <ul
          className="notification-menu-portal"
          style={{
            top: menuPos.top,
            left: menuPos.left,
          }}
          role="menu"
        >
          <li role="none">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              role="menuitem"
              className="notification-menu-item"
              onClick={(e) => {
                e.stopPropagation()
                setMenuOpenId(null)
                setMenuPos(null)
                void handleMarkRead(
                  menuN.id,
                )
              }}
              disabled={menuN.is_read}
            >
              {t('notifications.markRead')}
            </MotionPress>
          </li>
          <li role="none">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              role="menuitem"
              className="notification-menu-item"
              onClick={(e) => {
                e.stopPropagation()
                setMenuOpenId(null)
                setMenuPos(null)
                void handleMarkUnread(
                  menuN.id,
                )
              }}
              disabled={!menuN.is_read}
            >
              {t('notifications.markUnread')}
            </MotionPress>
          </li>
          <li role="none">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="medium"
              role="menuitem"
              className="notification-menu-item danger"
              onClick={(e) => {
                e.stopPropagation()
                void handleDelete(
                  menuN.id,
                )
              }}
            >
              {t('notifications.delete')}
            </MotionPress>
          </li>
        </ul>,
        document.body,
      )
    )

  const overlay = (
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
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            ariaLabel={t(
              'notifications.closeAria',
            )}
            onClick={onClose}
          >
            <Icon name="x" size={18} />
          </MotionPress>
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
                  <MotionPress
                    type="button"
                    variant="ghost"
                    haptic="light"
                    className={`notification-item${
                      n.is_read
                        ? ''
                        : ' unread'
                    }`}
                    onClick={() => {
                      void handleRowClick(n)
                    }}
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
                  </MotionPress>
                  <div className="notification-item-menu">
                    <MotionPress
                      type="button"
                      variant="icon"
                      haptic="light"
                      className="notification-more"
                      data-notif-menu-anchor={n.id}
                      ariaLabel={t(
                        'notifications.moreActions',
                      )}
                      aria-expanded={
                        menuOpenId === n.id
                      }
                      onClick={(e) => {
                        e.stopPropagation()
                        if (
                          menuOpenId ===
                          n.id
                        ) {
                          setMenuOpenId(null)
                          setMenuPos(
                            null,
                          )
                        } else {
                          setMenuOpenId(n.id)
                        }
                      }}
                    >
                      <Icon
                        name="more-vertical"
                        size={24}
                      />
                    </MotionPress>
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {menuPortal}
      </div>
    </div>
  )

  return createPortal(overlay, document.body)
}
