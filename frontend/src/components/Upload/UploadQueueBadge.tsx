import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { listJobs, pendingCount } from '@/lib/uploadQueue'

interface UploadQueueBadgeProps {
  pollIntervalMs?: number
}

export function UploadQueueBadge({
  pollIntervalMs = 4000,
}: UploadQueueBadgeProps) {
  const [count, setCount] = useState(0)
  const { t } = useTranslation()
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false

    const refresh = async () => {
      try {
        const n = await pendingCount()
        if (!cancelled) setCount(n)
      } catch {
        if (!cancelled) setCount(0)
      }
    }

    void refresh()
    const id = window.setInterval(refresh, pollIntervalMs)
    const onFocus = () => void refresh()
    window.addEventListener('focus', onFocus)
    return () => {
      cancelled = true
      window.clearInterval(id)
      window.removeEventListener('focus', onFocus)
    }
  }, [pollIntervalMs])

  if (count <= 0) return null

  return (
    <button
      type="button"
      className="dotsound-uqb"
      onClick={() => navigate('/upload?queue=1')}
      aria-label={t(
        'uploadQueue.badgeLabel',
        '{{n}} загрузок в очереди',
        { n: count },
      )}
    >
      <span className="dotsound-uqb__dot" aria-hidden />
      <span>
        {t('uploadQueue.badge', '{{n}} в очереди', { n: count })}
      </span>
    </button>
  )
}

export async function hasPendingUploads(): Promise<boolean> {
  return (await listJobs()).some(
    (j) =>
      j.status === 'pending' ||
      j.status === 'paused' ||
      j.status === 'failed',
  )
}

export default UploadQueueBadge
