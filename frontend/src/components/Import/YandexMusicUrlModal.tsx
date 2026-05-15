import { useEffect, useState, type MouseEvent } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

interface Props {
  open: boolean
  onClose: () => void
  onScan: (url: string) => Promise<void>
}

const URL_PREFIXES = [
  'https://music.yandex.ru/',
  'http://music.yandex.ru/',
]

export function YandexMusicUrlModal({
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
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [open, submitting, onClose])

  useEffect(() => {
    if (!open) {
      setUrl('')
      setError('')
      setSubmitting(false)
    }
  }, [open])

  if (!open) return null

  const handleBackdrop = (
    e: MouseEvent<HTMLDivElement>,
  ) => {
    if (e.target === e.currentTarget && !submitting) {
      onClose()
    }
  }

  const handleSubmit = async () => {
    const trimmed = url.trim()
    if (!trimmed) {
      setError('Вставьте ссылку на плейлист или альбом')
      return
    }
    if (!URL_PREFIXES.some((p) => trimmed.startsWith(p))) {
      setError(
        'Ссылка должна начинаться с https://music.yandex.ru/',
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
          ? 'Яндекс Музыка не смогла открыть ссылку. Проверьте, что плейлист или альбом доступен без авторизации.'
          : msg === '401'
            ? 'Требуется авторизация'
            : msg || 'Не удалось отсканировать ссылку. Попробуйте позже.',
      )
      setSubmitting(false)
    }
  }

  return (
    <div className="modal" onClick={handleBackdrop}>
      <div className="modal-content">
        <div className="modal-header">
          <h3>Импорт из Яндекс Музыки</h3>
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
          Откройте плейлист или альбом в Яндекс Музыке,
          скопируйте ссылку и вставьте её ниже. Поддерживаются
          ссылки вида <code>music.yandex.ru/users/.../playlists/...</code>
          {' '}или <code>music.yandex.ru/album/...</code>
        </p>
        <div className="form-group">
          <label className="form-label">
            Ссылка на плейлист или альбом
          </label>
          <input
            className="form-input"
            type="url"
            inputMode="url"
            autoComplete="off"
            placeholder="https://music.yandex.ru/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !submitting) {
                handleSubmit()
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
          onClick={handleSubmit}
        >
          {submitting ? 'Сканируем...' : 'Сканировать'}
        </MotionPress>
      </div>
    </div>
  )
}
