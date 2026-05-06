import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  dismissIsland,
  showIsland,
} from '@/lib/island'

export function OfflineBanner() {
  const { t } = useTranslation()
  const islandIdRef = useRef<string | null>(null)

  useEffect(() => {
    const sync = () => {
      const online =
        typeof navigator === 'undefined'
          ? true
          : navigator.onLine

      if (!online) {
        if (!islandIdRef.current) {
          islandIdRef.current = showIsland({
            kind: 'error',
            title: t(
              'redesign.nav.offlineTitle',
              'No connection',
            ),
            hint: t(
              'redesign.nav.offlineHint',
              'Check your network and try again.',
            ),
            durationMs: Number.POSITIVE_INFINITY,
          })
        }
        return
      }

      if (islandIdRef.current) {
        dismissIsland(islandIdRef.current)
        islandIdRef.current = null
      }
    }

    sync()
    window.addEventListener('online', sync)
    window.addEventListener('offline', sync)
    return () => {
      window.removeEventListener('online', sync)
      window.removeEventListener('offline', sync)
      if (islandIdRef.current) {
        dismissIsland(islandIdRef.current)
        islandIdRef.current = null
      }
    }
  }, [t])

  return null
}
