import { useState } from 'react'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import { showIsland } from '@/lib/island'

export function ProfileDebugMenu({
  serverDebug,
}: {
  serverDebug: boolean
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  if (!getIsAdmin() || !serverDebug) {
    return null
  }

  const resetOnboarding = async () => {
    if (busy) return
    setBusy(true)
    try {
      await api.debugResetOnboarding()
      showIsland({ kind: 'toast', title: 'Онбординг сброшен — перезагрузка…', durationMs: 2200 })
      window.setTimeout(() => {
        window.location.reload()
      }, 300)
    } catch {
      showIsland({ kind: 'error', title: 'Не удалось сбросить', durationMs: 3500 })
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
