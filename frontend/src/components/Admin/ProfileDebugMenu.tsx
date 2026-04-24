import { useState } from 'react'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import { useToast } from '@/components/ui/Toast'

export function ProfileDebugMenu({
  serverDebug,
}: {
  serverDebug: boolean
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  if (!getIsAdmin() || !serverDebug) {
    return null
  }

  const resetOnboarding = async () => {
    if (busy) return
    setBusy(true)
    try {
      await api.debugResetOnboarding()
      toast.info('Онбординг сброшен — перезагрузка…')
      window.setTimeout(() => {
        window.location.reload()
      }, 300)
    } catch {
      toast.error('Не удалось сбросить')
      setBusy(false)
    }
  }

  return (
    <div className="profile-debug-wrap">
      <button
        type="button"
        className="profile-debug-toggle"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        Дебаг
        <span className="profile-debug-chevron">
          {open ? '▾' : '▸'}
        </span>
      </button>
      {open && (
        <div className="profile-debug-panel">
          <button
            type="button"
            className="profile-debug-item"
            onClick={resetOnboarding}
            disabled={busy}
          >
            Снова пройти инициализацию
          </button>
        </div>
      )}
    </div>
  )
}
