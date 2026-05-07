import { useEffect, useState, type MouseEvent } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

interface Props {
  open: boolean
  onClose: () => void
  onScan: (url: string) => Promise<void>
}

const _SC_SETS = /soundcloud\.com\/[^/]+\/sets\//i

/** Allows full .../sets/... links, m.soundcloud.com, and on.soundcloud.com short links. */
function isPlausibleScPlaylistUrl(trimmed: string): boolean {
  try {
    const u = new URL(trimmed)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') {
      return false
    }
    const h = u.hostname.toLowerCase()
    if (h === 'api.soundcloud.com') {
      return false
    }
    if (h === 'on.soundcloud.com') {
      return u.pathname.length > 1
    }
    if (
      h === 'soundcloud.com' ||
      h === 'www.soundcloud.com' ||
      h === 'm.soundcloud.com'
    ) {
      return _SC_SETS.test(u.href)
    }
    if (h.endsWith('.soundcloud.com')) {
      return _SC_SETS.test(u.href)
    }
    return false
  } catch {
    return false
  }
}

export function SoundCloudPlaylistUrlModal({
  open,
  onClose,
  onScan,
}: Props) {
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
      setError('Вставьте ссылку на плейлист')
      return
    }
    if (!isPlausibleScPlaylistUrl(trimmed)) {
      setError(
        'Ссылка должна вести на публичный плейлист на soundcloud.com (в пути есть /sets/)',
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
          ? 'Не удалось открыть плейлист. Проверьте, что он публичный и ссылка полная.'
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
          <h3>Импорт из SoundCloud</h3>
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
          Публичный плейлист: ссылка с{' '}
          <code>…/sets/…</code> на soundcloud.com, либо короткая{' '}
          <code>on.soundcloud.com/…</code>. Один трек
          &nbsp;— в другом сценарии.
        </p>
        <div className="form-group">
          <label className="form-label">Ссылка на плейлист</label>
          <input
            className="form-input"
            type="url"
            inputMode="url"
            autoComplete="off"
            placeholder="https://on.soundcloud.com/… или …/sets/…"
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
