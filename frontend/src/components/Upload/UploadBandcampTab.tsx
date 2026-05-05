import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, getApiErrorMessage } from '@/lib/api'
import { hapticNotification, hapticSelection } from '@/lib/telegram'
import type { Track } from '@/types/api'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadBandcampTab({ onSuccess }: Props) {
  const { t } = useTranslation()
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
      hapticSelection()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      const isCode = /^[1-5]\d{2}$/.test(msg)
      setError(
        isCode
          ? t(`upload.errBandcamp.${msg}`, {
            defaultValue: t('upload.errBandcamp.def'),
          })
          : getApiErrorMessage(
            err,
            t('upload.errBandcamp.def'),
          ),
      )
      hapticNotification('error')
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    if (!preview) return
    hapticNotification('success')
    const track = preview
    setBcUrl('')
    setPreview(null)
    onSuccess(track)
  }

  return (
    <div className="sc-import-form">
      <div className="form-group">
        <label className="form-label">
          {t('upload.urlTrack')}
        </label>
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
        <label className="form-label">
          {t('upload.public')}
        </label>
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
        {loading
          ? t('upload.loading')
          : t('upload.getInfo')}
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
            {t('upload.addAndPlay')}
          </button>
        </div>
      )}
    </div>
  )
}
