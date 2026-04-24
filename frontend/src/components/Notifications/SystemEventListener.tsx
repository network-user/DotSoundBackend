import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { onWS } from '@/lib/ws'
import { useToast } from '@/components/ui/Toast'
import { hapticNotification } from '@/lib/telegram'
import {
  buildNotificationToastMessage,
} from '@/lib/notificationText'
import type { AppNotification } from '@/types/api'

interface NotificationEventData {
  event?: string
  type?: string
  title?: string
  body?: string
  reason?: string
  message?: string
  data?: Record<string, unknown> | null
}

const TOAST_BY_TYPE: Record<
  string,
  'info' | 'success' | 'warning' | 'error'
> = {
  account_warning: 'warning',
  account_banned: 'error',
  account_restored: 'success',
  complaint_resolved: 'success',
  complaint_dismissed: 'info',
  track_hidden: 'warning',
  track_restored: 'success',
  admin_message: 'info',
  import_completed: 'success',
  import_failed: 'error',
}

const HAPTIC_BY_TYPE: Record<
  string,
  'success' | 'warning' | 'error'
> = {
  account_warning: 'warning',
  account_banned: 'error',
  account_restored: 'success',
  complaint_resolved: 'success',
  track_hidden: 'warning',
  track_restored: 'success',
  import_completed: 'success',
  import_failed: 'error',
}

function eventToNotif(
  d: NotificationEventData,
): Pick<
  AppNotification,
  'type' | 'title' | 'body' | 'data'
> {
  const typ =
    d.type ||
    (d.data?.type as string | undefined) ||
    ''
  const t = (d.title || '').trim()
  const b = (
    d.body ||
    d.message ||
    ''
  ).trim()
  return {
    type: typ,
    title: t,
    body: b,
    data: d.data ?? null,
  }
}

export function SystemEventListener() {
  const toast = useToast()
  const { t } = useTranslation()

  useEffect(() => {
    const handle = (raw: Record<string, unknown>) => {
      const d = raw as NotificationEventData
      const nLike = eventToNotif(d)
      const message = buildNotificationToastMessage(
        nLike,
        t,
      )
      if (!nLike.type && !message) return
      const kind = TOAST_BY_TYPE[nLike.type] || 'info'
      const importToastOpts =
        nLike.type ===
          'import_completed' ||
        nLike.type === 'import_failed'
          ? { duration: 10_000 }
          : undefined
      if (kind === 'success') {
        toast.success(
          message || t('notifications.toast.fallbackSuccess'),
          importToastOpts,
        )
      } else if (kind === 'warning') {
        toast.warning(
          message || t('notifications.toast.fallbackWarning'),
          importToastOpts,
        )
      } else if (kind === 'error') {
        toast.error(
          message || t('notifications.toast.fallbackError'),
          importToastOpts,
        )
      } else {
        toast.info(
          message || t('notifications.toast.fallbackInfo'),
          importToastOpts,
        )
      }
      const haptic = HAPTIC_BY_TYPE[nLike.type]
      if (haptic) hapticNotification(haptic)
    }

    const offNotif = onWS('notification', handle)
    const offTrackHidden = onWS('track.hidden', (d) =>
      handle({ ...d, type: 'track_hidden' }),
    )
    const offComplaint = onWS(
      'complaint.resolved',
      (d) =>
        handle({
          ...d,
          type: 'complaint_resolved',
        }),
    )
    const offWarning = onWS(
      'account.warning',
      (d) =>
        handle({
          ...d,
          type: 'account_warning',
        }),
    )

    return () => {
      offNotif()
      offTrackHidden()
      offComplaint()
      offWarning()
    }
  }, [toast, t])

  return null
}
