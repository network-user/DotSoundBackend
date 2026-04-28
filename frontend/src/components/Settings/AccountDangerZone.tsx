import { useState } from 'react'
import { api } from '@/lib/api'

export function AccountDangerZone() {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (text.trim() !== 'DELETE') return
    setLoading(true)
    try {
      await api.requestAccountDeletion('DELETE')
      api.logout()
      window.location.reload()
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ marginTop: 20 }}>
      <div className="settings-hint">Аккаунт</div>
      {!open ? (
        <button
          type="button"
          className="settings-item"
          onClick={() => setOpen(true)}
          style={{
            color: 'var(--danger, #c44)',
          }}
        >
          Удалить аккаунт…
        </button>
      ) : (
        <div style={{ padding: '8px 0' }}>
          <p className="twofa-hint">
            Введите DELETE для подтверждения удаления
            аккаунта.
          </p>
          <input
            className="form-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="DELETE"
            autoComplete="off"
          />
          <div
            style={{
              display: 'flex',
              gap: 8,
              marginTop: 8,
            }}
          >
            <button
              type="button"
              className="btn-primary"
              disabled={
                loading || text.trim() !== 'DELETE'
              }
              onClick={() => void submit()}
            >
              {loading ? '…' : 'Подтвердить'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={loading}
              onClick={() => {
                setOpen(false)
                setText('')
              }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
