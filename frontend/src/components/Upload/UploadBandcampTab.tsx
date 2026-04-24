import { useState } from 'react'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadBandcampTab({ onSuccess }: Props) {
  const [bcUrl, setBcUrl] = useState('')
  const [preview, setPreview] = useState<Track | null>(null)
  const [loading, setLoading] = useState(false)
  const [isPublic, setIsPublic] = useState(true)
  const [error, setError] = useState('')

  const handlePreview = async () => {
    if (!bcUrl.trim()) return
    setError('')
    setPreview(null)
    setLoading(true)
    try {
      const track = await api.importBandcampTrack(bcUrl.trim(), isPublic)
      setPreview(track)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      setError(
        msg === '400' ? 'Неверная ссылка. Вставьте URL трека с bandcamp.com' :
        msg === '402' ? 'Этот трек требует покупки на Bandcamp и недоступен для стриминга' :
        msg === '404' ? 'Трек не найден или удалён' :
        msg === '422' ? 'Не удалось получить данные трека. Проверьте, что ссылка ведёт на отдельный трек.' :
        'Ошибка. Проверьте ссылку.',
      )
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    if (!preview) return
    const track = preview
    setBcUrl('')
    setPreview(null)
    onSuccess(track)
  }

  return (
    <div className="sc-import-form">
      <div className="form-group">
        <label className="form-label">Ссылка на трек</label>
        <input
          className="form-input"
          type="url"
          placeholder="https://artist.bandcamp.com/track/track-name"
          value={bcUrl}
          onChange={(e) => {
            setBcUrl(e.target.value)
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
        disabled={loading || !bcUrl.trim()}
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
