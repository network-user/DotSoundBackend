import { useEffect, useState, type MouseEvent } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

interface Props {
  open: boolean
  onClose: () => void
  onScan: (url: string) => Promise<void>
}

function isPlausibleSpotifyUrl(trimmed: string): boolean {
  try {
    const u = new URL(trimmed)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') {
      return false
    }
    if (u.hostname.toLowerCase() !== 'open.spotify.com') {
      return false
    }
    const path = (u.pathname || '/').toLowerCase()
    return path.startsWith('/playlist/') || path.startsWith('/album/')
  } catch {
    return false
  }
}

export function SpotifyUrlModal({ open, onClose, onScan }: Props) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, submitting, onClose])

  useEffect(() => {
    if (!open) {
      setUrl('')
      setError('')
      setSubmitting(false)
    }
  }, [open])

  if (!open) return null

  const handleBackdrop = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !submitting) onClose()
  }

  const handleSubmit = async () => {
    const trimmed = url.trim()
    if (!trimmed) {
      setError('Вставьте ссылку на плейлист или альбом')
      return
    }
    if (!isPlausibleSpotifyUrl(trimmed)) {
      setError(
        'Ссылка должна быть open.spotify.com/playlist/... или open.spotify.com/album/...',
      )
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await onScan(trimmed)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      setError(
        msg === '400'
          ? 'Не удалось открыть ссылку. Плейлист или альбом должны быть публичны.'
          : msg === '401'
            ? 'Требуется авторизация'
            : 'Не удалось отсканировать ссылку. Попробуйте позже.',
      )
      setSubmitting(false)
    }
  }

  return (
    <div className="modal" onClick={handleBackdrop}>
      <div className="modal-content">
        <div className="modal-header">
          <h3>Импорт из Spotify</h3>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn"
            ariaLabel="Закрыть"
            onClick={onClose}
            disabled={submitting}
          >
            <Icon name="x" size={18} />
          </MotionPress>
        </div>
        <p className="modal-hint">
          Откройте плейлист или альбом в Spotify (в браузере), в меню
          &nbsp;«Поделиться» выберите «Ссылка» и вставьте её
          {'. '}
        </p>
        <div className="form-group">
          <label className="form-label">Ссылка</label>
          <input
            className="form-input"
            type="url"
            inputMode="url"
            autoComplete="off"
            placeholder="https://open.spotify.com/playlist/…"
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !submitting) {
                void handleSubmit()
              }
            }}
            disabled={submitting}
            autoFocus
          />
        </div>
        {error && <div className="form-error">{error}</div>}
        <MotionPress
          type="button"
          variant="primary"
          haptic="medium"
          className="btn-primary"
          disabled={submitting}
          onClick={() => void handleSubmit()}
        >
          {submitting ? 'Сканируем...' : 'Сканировать'}
        </MotionPress>
      </div>
    </div>
  )
}
