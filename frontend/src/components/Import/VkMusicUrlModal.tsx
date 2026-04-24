import { useEffect, useState, type MouseEvent } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  open: boolean
  onClose: () => void
  onScan: (url: string) => Promise<void>
}

/** Match backend `is_allowed_vk_music_url` (registrable vk.com, not notvk.com). */
function isPlausibleVkUrl(trimmed: string): boolean {
  try {
    const u = new URL(trimmed)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') {
      return false
    }
    const h = u.hostname.toLowerCase()
    const p = h.split('.')
    return p.length >= 2 && p[p.length - 2] === 'vk' && p[p.length - 1] === 'com'
  } catch {
    return false
  }
}

export function VkMusicUrlModal({ open, onClose, onScan }: Props) {
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
    if (e.target === e.currentTarget && !submitting) {
      onClose()
    }
  }

  const handleSubmit = async () => {
    const trimmed = url.trim()
    if (!trimmed) {
      setError('Вставьте ссылку (альбом, плейлист, аудиозаписи)')
      return
    }
    if (!isPlausibleVkUrl(trimmed)) {
      setError('Ссылка должна вести на vk.com (m.vk.com, music.vk.com и т.д.)')
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
          ? 'Сервис не смог открыть ссылку. Проверьте, что страница публично доступна.'
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
          <h3>Импорт из VK Музыка</h3>
          <button
            className="icon-btn"
            onClick={onClose}
            disabled={submitting}
            aria-label="Закрыть"
          >
            <Icon name="x" size={18} />
          </button>
        </div>
        <p className="modal-hint">
          Вставьте ссылку из VK как в адресной строке (с компьютера
          или телефона): альбом{' '}
          <code>vk.com/music/album/...</code>, плейлист —{' '}
          <code>.../music/playlist/...</code> или
          <code>…/audios…</code> из раздела с аудиозаписями.
          Ссылка будет нормализована на сервере.
        </p>
        <div className="form-group">
          <label className="form-label">Ссылка на VK</label>
          <input
            className="form-input"
            type="url"
            inputMode="url"
            autoComplete="off"
            placeholder="https://vk.com/…"
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !submitting) {
                handleSubmit()
              }
            }}
            disabled={submitting}
            autoFocus
          />
        </div>
        {error && <div className="form-error">{error}</div>}
        <button
          className="btn-primary"
          disabled={submitting}
          onClick={handleSubmit}
        >
          {submitting ? 'Сканируем...' : 'Сканировать'}
        </button>
      </div>
    </div>
  )
}
