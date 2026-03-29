import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import type { ViewName } from '@/components/BottomNav/BottomNav'
import type { Track } from '@/types/api'

interface Props {
  active: boolean
  onNavigate: (view: ViewName) => void
}

type Tab = 'file' | 'soundcloud'

export function UploadView({ active, onNavigate }: Props) {
  const { playTrack } = usePlayer()
  const [tab, setTab] = useState<Tab>('file')

  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState(true)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [scUrl, setSCUrl] = useState('')
  const [scPreview, setSCPreview] = useState<Track | null>(null)
  const [scLoading, setSCLoading] = useState(false)
  const [scPublic, setSCPublic] = useState(true)
  const [scError, setSCError] = useState('')

  const handleCoverChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null
    setCoverFile(file)
    if (file) {
      const reader = new FileReader()
      reader.onload = (ev) => setCoverPreview(ev.target?.result as string)
      reader.readAsDataURL(file)
    } else {
      setCoverPreview(null)
    }
  }

  const animateProgress = () => {
    setProgress(0)
    progressTimerRef.current = setInterval(() => {
      setProgress((prev) => {
        const next = Math.min(prev + Math.random() * 12, 85)
        if (next >= 85 && progressTimerRef.current) {
          clearInterval(progressTimerRef.current)
        }
        return next
      })
    }, 300)
  }

  const stopProgress = () => {
    if (progressTimerRef.current) clearInterval(progressTimerRef.current)
    progressTimerRef.current = null
  }

  const reset = () => {
    setTitle('')
    setArtist('')
    setAudioFile(null)
    setCoverFile(null)
    setCoverPreview(null)
    setError('')
    setProgress(0)
    setIsPublic(true)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!title.trim()) { setError('Введите название трека'); return }
    if (!audioFile) { setError('Выберите аудиофайл'); return }

    setUploading(true)
    animateProgress()

    try {
      const fd = new FormData()
      fd.append('file', audioFile)
      fd.append('title', title.trim())
      if (artist.trim()) fd.append('artist', artist.trim())
      if (coverFile) fd.append('cover', coverFile)
      if (userId) fd.append('uploader_id', String(userId))
      fd.append('is_public', String(isPublic))

      const uploaded = await api.uploadTrack(fd)
      stopProgress()
      setProgress(100)

      setTimeout(async () => {
        reset()
        onNavigate('home')
        const fullTrack = await api.getTrack(uploaded.id)
        playTrack(fullTrack)
      }, 600)
    } catch (err: unknown) {
      stopProgress()
      setProgress(0)
      setUploading(false)
      const msg = err instanceof Error ? err.message : ''
      setError(
        msg === '415' ? 'Формат файла не поддерживается' :
        msg === '413' ? 'Файл слишком большой (макс. 50 МБ)' :
        'Ошибка загрузки. Попробуй ещё раз.',
      )
    }
  }

  const handleSCPreview = async () => {
    if (!scUrl.trim()) return
    setSCError('')
    setSCPreview(null)
    setSCLoading(true)
    try {
      const track = await api.importSCTrack(
        scUrl.trim(),
        userId ?? undefined,
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

  const handleSCAdd = async () => {
    if (!scPreview) return
    onNavigate('home')
    await playTrack(scPreview)
    setSCUrl('')
    setSCPreview(null)
  }

  return (
    <section id="view-upload" className={`view${active ? ' active' : ''}`}>
      <div className="view-header"><h2>Загрузить трек</h2></div>

      <div className="upload-tabs">
        <button
          className={`upload-tab${tab === 'file' ? ' active' : ''}`}
          onClick={() => setTab('file')}
        >
          Файл
        </button>
        <button
          className={`upload-tab${tab === 'soundcloud' ? ' active' : ''}`}
          onClick={() => setTab('soundcloud')}
        >
          SoundCloud
        </button>
      </div>

      {tab === 'file' && (
        <form id="upload-form" noValidate onSubmit={handleSubmit}>
          <label className="cover-picker" htmlFor="cover-input">
            <div className="cover-preview">
              {coverPreview
                ? <img src={coverPreview} alt="cover" />
                : <span className="cover-placeholder">🎵</span>
              }
            </div>
            <span className="cover-label">Добавить обложку</span>
          </label>
          <input
            id="cover-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={handleCoverChange}
          />

          <div className="form-group">
            <label className="form-label" htmlFor="title-input">Название *</label>
            <input
              id="title-input"
              className="form-input"
              type="text"
              placeholder="Название трека"
              maxLength={256}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="artist-input">Исполнитель</label>
            <input
              id="artist-input"
              className="form-input"
              type="text"
              placeholder="Имя исполнителя"
              maxLength={256}
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Аудиофайл *</label>
            <label className="file-pick-btn" htmlFor="audio-input">
              <span>📁</span> Выбрать файл
            </label>
            <p className="file-name">{audioFile ? audioFile.name : 'Файл не выбран'}</p>
            <input
              id="audio-input"
              type="file"
              accept="audio/mpeg,audio/ogg,audio/wav,audio/flac,audio/mp4,audio/aac"
              hidden
              onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
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

          {error && <div className="form-error">{error}</div>}

          <button type="submit" className="btn-primary" disabled={uploading}>
            Загрузить
          </button>

          {uploading && (
            <div>
              <div className="progress-bar-wrap">
                <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
              </div>
              <p className="progress-label">Загрузка…</p>
            </div>
          )}
        </form>
      )}

      {tab === 'soundcloud' && (
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
      )}
    </section>
  )
}
