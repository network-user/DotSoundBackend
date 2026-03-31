import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import type { LyricsResponse, Track } from '@/types/api'
import { LyricsEditor } from '../TrackCardSheet/LyricsEditor'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadFileTab({ onSuccess }: Props) {
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [genre, setGenre] = useState('')
  const [genres, setGenres] = useState<string[]>([])
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState(true)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [lyrics, setLyrics] = useState<LyricsResponse | null>(null)
  const [showLyricsEditor, setShowLyricsEditor] = useState(false)
  const [localAudioUrl, setLocalAudioUrl] = useState<string | null>(null)
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    api.getGenres().then(setGenres).catch(() => {})
  }, [])

  useEffect(() => {
    return () => {
      if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
    }
  }, [localAudioUrl])

  const handleAudioChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null
    setAudioFile(file)
    if (file) {
      if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
      setLocalAudioUrl(URL.createObjectURL(file))
    }
  }

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
    setGenre('')
    setAudioFile(null)
    setCoverFile(null)
    setCoverPreview(null)
    setLyrics(null)
    setLocalAudioUrl(null)
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
      if (genre.trim()) fd.append('genre', genre.trim())
      if (coverFile) fd.append('cover', coverFile)
      if (userId) fd.append('uploader_id', String(userId))
      fd.append('is_public', String(isPublic))

      const uploaded = await api.uploadTrack(fd)

      // Save lyrics if provided
      if (lyrics) {
        if (lyrics.synced_lines) {
          await api.saveLyricsSync(uploaded.id, lyrics.synced_lines)
        } else {
          await api.saveLyrics(uploaded.id, lyrics.plain_text)
        }
      }
      stopProgress()
      setProgress(100)

      setTimeout(async () => {
        reset()
        const fullTrack = await api.getTrack(uploaded.id)
        onSuccess(fullTrack)
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
        <label className="form-label" htmlFor="genre-input">Жанр</label>
        <input
          id="genre-input"
          className="form-input"
          type="text"
          list="genres-list"
          placeholder="Выбери или введи свой"
          value={genre}
          onChange={(e) => setGenre(e.target.value)}
        />
        <datalist id="genres-list">
          {genres.map((g) => <option key={g} value={g} />)}
        </datalist>
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
          onChange={handleAudioChange}
        />
      </div>

      {audioFile && (
        <div className="form-group">
          <label className="form-label">Текст песни</label>
          <button
            type="button"
            className={`lyrics-editor-trigger${lyrics ? ' active' : ''}`}
            onClick={() => setShowLyricsEditor(true)}
          >
            {lyrics ? '✅ Текст добавлен (изменить)' : '📝 Добавить текст / таймкоды'}
          </button>
        </div>
      )}

      {showLyricsEditor && localAudioUrl && (
        <div className="fullscreen-overlay">
          <div className="overlay-content">
            <LyricsEditor
              localAudioUrl={localAudioUrl}
              existingLyrics={lyrics}
              onSaved={(l) => {
                setLyrics(l)
                setShowLyricsEditor(false)
              }}
              onCancel={() => setShowLyricsEditor(false)}
            />
          </div>
        </div>
      )}

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
  )
}
