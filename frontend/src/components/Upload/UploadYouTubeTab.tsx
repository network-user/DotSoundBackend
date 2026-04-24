import { useState } from 'react'
import { api, getApiErrorMessage } from '@/lib/api'
import type { Track } from '@/types/api'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadYouTubeTab({ onSuccess }: Props) {
  const [ytUrl, setYtUrl] = useState('')
  const [preview, setPreview] = useState<Track | null>(null)
  const [loading, setLoading] = useState(false)
  const [isPublic, setIsPublic] = useState(true)
  const [error, setError] = useState('')

  const handlePreview = async () => {
    if (!ytUrl.trim()) return
    setError('')
    setPreview(null)
    setLoading(true)
    try {
      const track = await api.importYouTubeTrack(ytUrl.trim(), isPublic)
      setPreview(track)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      const isCode = /^[1-5]\d{2}$/.test(msg)
      setError(
        isCode ? (
          msg === '400' ? 'Неверная ссылка. Вставьте URL видео с youtube.com или youtu.be' :
          msg === '404' ? 'Видео не найдено или недоступно' :
          msg === '422' ? 'Не удалось получить аудио-поток. Возможно, видео ограничено.' :
          msg === '503' ? 'YouTube временно недоступен. Попробуйте позже.' :
          'Ошибка. Проверьте ссылку.'
        ) : getApiErrorMessage(err, 'Ошибка. Проверьте ссылку.'),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    if (!preview) return
    const track = preview
    setYtUrl('')
    setPreview(null)
    onSuccess(track)
  }

  return (
    <div className="sc-import-form">
      <div className="form-group">
        <label className="form-label">Ссылка на видео</label>
        <input
          className="form-input"
          type="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={ytUrl}
          onChange={(e) => {
            setYtUrl(e.target.value)
            setPreview(null)
            setError('')
          }}
        />
      </div>

      <div className="form-group form-group-row">
        <label className="form-label">Публичный</label>
        <input
          type="checkbox"
          checked={isPublic}
          onChange={(e) => setIsPublic(e.target.checked)}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handlePreview}
        disabled={loading || !ytUrl.trim()}
      >
        {loading ? 'Загрузка…' : 'Получить информацию'}
      </button>

      {error && <div className="form-error">{error}</div>}

      {preview && (
        <div className="sc-preview">
          {preview.cover_key && (
            <img
              src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(preview.cover_key)}`}
              alt="cover"
              className="sc-preview-cover"
            />
          )}
          <div className="sc-preview-info">
            <p className="sc-preview-title">{preview.title}</p>
            <p className="sc-preview-artist">{preview.artist}</p>
          </div>
          <button className="btn-primary" onClick={handleAdd}>
            Добавить и слушать
          </button>
        </div>
      )}
    </div>
  )
}
