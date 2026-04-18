import { useEffect, useState } from 'react'

export function OfflineBanner() {
  const [online, setOnline] = useState<boolean>(
    () =>
      typeof navigator === 'undefined'
        ? true
        : navigator.onLine,
  )

  useEffect(() => {
    const goOnline = () => setOnline(true)
    const goOffline = () => setOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener(
        'online',
        goOnline,
      )
      window.removeEventListener(
        'offline',
        goOffline,
      )
    }
  }, [])

  if (online) return null

  return (
    <div
      className="offline-banner"
      role="status"
      aria-live="polite"
    >
      Нет соединения
    </div>
  )
}
