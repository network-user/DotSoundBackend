import { useState } from 'react'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import type { Track } from '@/types/api'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadSoundCloudTab({ onSuccess }: Props) {
  const [scUrl, setSCUrl] = useState('')
  const [scPreview, setSCPreview] = useState<Track | null>(null)
  const [scLoading, setSCLoading] = useState(false)
  const [scPublic, setSCPublic] = useState(true)
  const [scError, setSCError] = useState('')

  const handleSCPreview = async () => {
    if (!scUrl.trim()) return
    setSCError('')
    setSCPreview(null)
    setSCLoading(true)
    try {
      const track = await api.importSCTrack(
        scUrl.trim(),
        getUserId() ?? undefined,
        scPublic,
      )
      setSCPreview(track)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      setSCError(
        msg === '400' ? 'Неверная ссылка. Вставьте URL трека с soundcloud.com' :
        msg === '404' ? 'Трек не найден или приватный' :
        msg === '503' ? 'SC_CLIENT_ID не настроен' :
        'Ошибка. Проверь ссылку.',
      )
    } finally {
      setSCLoading(false)
    }
  }

  const handleSCAdd = () => {
    if (!scPreview) return
    const track = scPreview
    setSCUrl('')
    setSCPreview(null)
    onSuccess(track)
  }

  return (
    <div className="sc-import-form">
      <div className="form-group">
        <label className="form-label">Ссылка на трек</label>
        <input
          className="form-input"
          type="url"
          placeholder="https://soundcloud.com/artist/track"
          value={scUrl}
          onChange={(e) => {
            setSCUrl(e.target.value)
            setSCPreview(null)
            setSCError('')
          }}
        />
      </div>

      <div className="form-group form-group-row">
        <label className="form-label">Публичный</label>
        <input
          type="checkbox"
          checked={scPublic}
          onChange={(e) => setSCPublic(e.target.checked)}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handleSCPreview}
        disabled={scLoading || !scUrl.trim()}
      >
        {scLoading ? 'Загрузка…' : 'Получить информацию'}
      </button>

      {scError && <div className="form-error">{scError}</div>}

      {scPreview && (
        <div className="sc-preview">
          {scPreview.cover_key && (
            <img
              src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(scPreview.cover_key)}`}
              alt="cover"
              className="sc-preview-cover"
            />
          )}
          <div className="sc-preview-info">
            <p className="sc-preview-title">{scPreview.title}</p>
            <p className="sc-preview-artist">{scPreview.artist}</p>
          </div>
          <button className="btn-primary" onClick={handleSCAdd}>
            Добавить и слушать
          </button>
        </div>
      )}
    </div>
  )
}
