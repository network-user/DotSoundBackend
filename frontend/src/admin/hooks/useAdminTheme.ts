import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'dotsound:admin:theme'

export type AdminTheme = 'dark' | 'light'

function readStored(): AdminTheme {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    /* private mode */
  }
  return 'dark'
}

export function useAdminTheme() {
  const [theme, setTheme] = useState<AdminTheme>(readStored)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      /* private mode */
    }
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, setTheme, toggle }
}
