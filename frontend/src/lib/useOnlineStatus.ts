import { useEffect, useState } from 'react'

function readOnline(): boolean {
  if (typeof navigator === 'undefined') return true
  return navigator.onLine !== false
}

export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState<boolean>(readOnline)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const onOnline = () => setOnline(true)
    const onOffline = () => setOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  return online
}
