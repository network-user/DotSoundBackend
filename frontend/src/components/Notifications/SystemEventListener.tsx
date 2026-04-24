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
      const t = (data.title || '').trim()
      const b = (data.body || data.message || '').trim()
      let message = b
      if (!message)
        message =
          t ||
          (data.data?.body as string | undefined) ||
          (data.data?.title as string | undefined) ||
          ''
      else if (
        t &&
        (type === 'import_completed' || type === 'import_failed')
      ) {
        message = `${t}. ${b}`
      }
      if (!type && !message) return
      const kind = TOAST_BY_TYPE[type] || 'info'
      const importToastOpts =
        type === 'import_completed' || type === 'import_failed'
          ? { duration: 10_000 }
          : undefined
      if (kind === 'success')
        toast.success(message || 'Успех', importToastOpts)
      else if (kind === 'warning')
        toast.warning(
          message || 'Предупреждение',
          importToastOpts,
        )
      else if (kind === 'error')
        toast.error(message || 'Ошибка', importToastOpts)
      else
        toast.info(
          message || 'Уведомление',
          importToastOpts,
        )
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
