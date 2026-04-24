import { useEffect } from 'react'
import { onWS } from '@/lib/ws'
import { useToast } from '@/components/ui/Toast'
import { hapticNotification } from '@/lib/telegram'

interface NotificationEventData {
  event?: string
  type?: string
  title?: string
  body?: string
  reason?: string
  message?: string
  data?: Record<string, unknown>
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

export function SystemEventListener() {
  const toast = useToast()

  useEffect(() => {
    const handle = (raw: Record<string, unknown>) => {
      const data = raw as NotificationEventData
      const type =
        data.type ||
        (data.data?.type as string | undefined) ||
        ''
      const message =
        data.body ||
        data.message ||
        data.title ||
        (data.data?.body as string | undefined) ||
        (data.data?.title as string | undefined) ||
        ''
      if (!type && !message) return
      const kind = TOAST_BY_TYPE[type] || 'info'
      if (kind === 'success')
        toast.success(message || 'Успех')
      else if (kind === 'warning')
        toast.warning(message || 'Предупреждение')
      else if (kind === 'error')
        toast.error(message || 'Ошибка')
      else toast.info(message || 'Уведомление')
      const haptic = HAPTIC_BY_TYPE[type]
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
  }, [toast])

  return null
}
