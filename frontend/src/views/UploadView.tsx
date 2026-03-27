import { useRef, useState } from 'react'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import type { ViewName } from '@/components/BottomNav/BottomNav'

interface Props {
  active: boolean
  onNavigate: (view: ViewName) => void
}

export function UploadView({ active, onNavigate }: Props) {
  const { playTrack } = usePlayer()
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const handleCoverChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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
  }

  const handleSubmit = async (e: React.FormEvent) => {
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

  return (
    <section id="view-upload" className={`view${active ? ' active' : ''}`}>
      <div className="view-header"><h2>Загрузить трек</h2></div>
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
    </section>
  )
}
