import {
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
} from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { haptic, hapticNotification, hapticSelection } from '@/lib/telegram'
import type { LyricsResponse, Track } from '@/types/api'
import { LyricsEditor } from '../TrackCardSheet/LyricsEditor'

interface Props {
  onSuccess: (track: Track) => void
}

function fmtDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

const ALLOWED_AUDIO_TYPES = ['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/flac', 'audio/mp4', 'audio/aac']
const MAX_AUDIO_BYTES = 50 * 1024 * 1024

export function UploadFileTab({ onSuccess }: Props) {
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [genre, setGenre] = useState('')
  const [genreQuery, setGenreQuery] = useState('')
  const [genreOpen, setGenreOpen] = useState(false)
  const [genreSearching, setGenreSearching] = useState(false)
  const [genreResults, setGenreResults] = useState<string[]>([])
  const [genres, setGenres] = useState<string[]>([])
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [audioDuration, setAudioDuration] = useState<number | null>(null)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState(true)
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadDone, setUploadDone] = useState(false)
  const [lyrics, setLyrics] = useState<LyricsResponse | null>(null)
  const [showLyricsEditor, setShowLyricsEditor] = useState(false)
  const [localAudioUrl, setLocalAudioUrl] = useState<string | null>(null)
  const [coverDragging, setCoverDragging] = useState(false)
  const [audioDragging, setAudioDragging] = useState(false)

  useEffect(() => {
    api.getGenres().then(setGenres).catch(() => {})
  }, [])

  const normalizedGenres = useMemo(
    () => new Map(genres.map((g) => [g.toLowerCase(), g])),
    [genres],
  )

  useEffect(() => {
    const query = genreQuery.trim()
    if (!genreOpen || !query) {
      setGenreResults([])
      setGenreSearching(false)
      return
    }

    let cancelled = false
    const timer = window.setTimeout(() => {
      setGenreSearching(true)
      void (async () => {
        const byName = genres
          .filter((g) => g.toLowerCase().includes(query.toLowerCase()))
          .slice(0, 8)
        const searchHits = await api
          .getTracks({ q: query, size: 30 })
          .catch(() => ({ items: [] as Track[] }))
        const genresFromEs = searchHits.items
          .map((t) => t.genre?.trim() ?? '')
          .filter((x) => x.length > 0)
        const merged = [...byName, ...genresFromEs]
        const seen = new Set<string>()
        const result: string[] = []
        for (const item of merged) {
          const key = item.toLowerCase()
          if (seen.has(key)) {
            continue
          }
          seen.add(key)
          result.push(normalizedGenres.get(key) ?? item)
          if (result.length >= 10) {
            break
          }
        }
        const exact = normalizedGenres.get(query.toLowerCase())
        if (
          exact
          && !result.some((value) => value.toLowerCase() === exact.toLowerCase())
        ) {
          result.unshift(exact)
        }
        if (!cancelled) {
          setGenreResults(result)
          setGenreSearching(false)
        }
      })()
    }, 220)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [genreOpen, genreQuery, genres, normalizedGenres])

  const hasExactGenre = useMemo(
    () => normalizedGenres.has(genreQuery.trim().toLowerCase()),
    [genreQuery, normalizedGenres],
  )

  useEffect(() => {
    return () => {
      if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
    }
  }, [localAudioUrl])

  const applyAudioFile = (file: File) => {
    if (!ALLOWED_AUDIO_TYPES.includes(file.type)) {
      setError('Формат файла не поддерживается')
      hapticNotification('error')
      return
    }
    if (file.size > MAX_AUDIO_BYTES) {
      setError('Файл слишком большой (макс. 50 МБ)')
      hapticNotification('error')
      return
    }
    setError('')
    setAudioFile(file)
    hapticSelection()
    if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
    const url = URL.createObjectURL(file)
    setLocalAudioUrl(url)

    const tmp = new Audio()
    tmp.preload = 'metadata'
    tmp.src = url
    tmp.onloadedmetadata = () => {
      setAudioDuration(tmp.duration)
    }
  }

  const handleAudioChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) applyAudioFile(file)
  }

  const applyCoverFile = (file: File) => {
    if (!file.type.startsWith('image/')) return
    setCoverFile(file)
    hapticSelection()
    const reader = new FileReader()
    reader.onload = (ev) => setCoverPreview(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  const handleCoverChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) applyCoverFile(file)
    else { setCoverFile(null); setCoverPreview(null) }
  }

  const reset = () => {
    setTitle('')
    setArtist('')
    setGenre('')
    setGenreQuery('')
    setGenreOpen(false)
    setGenreSearching(false)
    setGenreResults([])
    setAudioFile(null)
    setAudioDuration(null)
    setCoverFile(null)
    setCoverPreview(null)
    setLyrics(null)
    setLocalAudioUrl(null)
    setError('')
    setUploading(false)
    setUploadDone(false)
    setIsPublic(true)
    setTermsAccepted(false)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (genreQuery.trim()) {
      const exact = normalizedGenres.get(genreQuery.trim().toLowerCase())
      setGenre(exact ?? genreQuery.trim())
    }

    if (!title.trim()) { setError('Введите название трека'); return }
    if (!audioFile) { setError('Выберите аудиофайл'); return }
    if (!termsAccepted) {
      setError('Подтвердите права на контент и согласие с условиями загрузки')
      return
    }

    setUploading(true)
    setUploadDone(false)

    try {
      const fd = new FormData()
      fd.append('file', audioFile)
      fd.append('title', title.trim())
      if (artist.trim()) fd.append('artist', artist.trim())
      if (genre.trim()) fd.append('genre', genre.trim())
      if (coverFile) fd.append('cover', coverFile)
      fd.append('is_public', String(isPublic))
      fd.append('upload_terms_accepted', 'true')

      const uploaded = await api.uploadTrack(fd)

      if (lyrics) {
        if (lyrics.synced_lines) {
          await api.saveLyricsSync(uploaded.id, lyrics.synced_lines)
        } else {
          await api.saveLyrics(uploaded.id, lyrics.plain_text)
        }
      }
      setUploadDone(true)
      hapticNotification('success')

      setTimeout(async () => {
        const fullTrack = await api.getTrack(uploaded.id)
        reset()
        onSuccess(fullTrack)
      }, 600)
    } catch (err: unknown) {
      setUploading(false)
      setUploadDone(false)
      const msg = err instanceof Error ? err.message : ''
      setError(
        msg === '415' ? 'Формат файла не поддерживается' :
        msg === '413' ? 'Файл слишком большой (макс. 50 МБ)' :
        'Ошибка загрузки. Попробуй ещё раз.',
      )
      hapticNotification('error')
    }
  }

  return (
    <form id="upload-form" noValidate onSubmit={handleSubmit}>
      <label
        className={`cover-picker${coverDragging ? ' drag-over' : ''}`}
        htmlFor="cover-input"
        onDragOver={(e) => { e.preventDefault(); setCoverDragging(true) }}
        onDragEnter={(e) => { e.preventDefault(); setCoverDragging(true) }}
        onDragLeave={() => setCoverDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setCoverDragging(false)
          const file = e.dataTransfer.files[0]
          if (file) applyCoverFile(file)
        }}
      >
        <div className="cover-preview">
          {coverPreview
            ? <img src={coverPreview} alt="cover" />
            : <span className="cover-placeholder">Track</span>
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

      <div className="form-group genre-search-group">
        <label className="form-label">Жанр</label>
        <button
          type="button"
          className="genre-search-toggle"
          onClick={() => {
            setGenreOpen((prev) => !prev)
            hapticSelection()
          }}
        >
          <Icon name="search" size={16} />
          <span>{genre || 'Поиск жанра'}</span>
          <Icon name={genreOpen ? 'chevron-up' : 'chevron-down'} size={16} />
        </button>
        {genreOpen && (
          <div className="genre-search-popover" role="listbox">
            <input
              className="form-input genre-search-input"
              placeholder="Начни вводить жанр"
              value={genreQuery}
              onChange={(e) => {
                const next = e.target.value
                setGenreQuery(next)
                if (next.trim()) {
                  setGenre(next.trim())
                }
              }}
            />
            {genreSearching && (
              <p className="genre-search-note">Ищем похожие жанры…</p>
            )}
            {!genreSearching && genreResults.length > 0 && (
              <div className="genre-search-list">
                {genreResults.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className={`genre-search-item${
                      genre.toLowerCase() === item.toLowerCase()
                        ? ' active'
                        : ''
                    }`}
                    onClick={() => {
                      setGenre(item)
                      setGenreQuery(item)
                      setGenreOpen(false)
                      hapticSelection()
                    }}
                  >
                    {item}
                  </button>
                ))}
              </div>
            )}
            {!genreSearching && genreQuery.trim() && !hasExactGenre && (
              <button
                type="button"
                className="genre-search-create"
                onClick={() => {
                  const custom = genreQuery.trim()
                  setGenre(custom)
                  setGenreQuery(custom)
                  setGenreOpen(false)
                  haptic('medium')
                }}
              >
                Создать жанр: {genreQuery.trim()}
              </button>
            )}
            {!genreSearching && genreResults.length === 0 && !genreQuery.trim() && (
              <p className="genre-search-note">
                Популярные жанры появятся после ввода.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="form-group">
        <label className="form-label">Аудиофайл *</label>
        <div
          className={`audio-drop-zone${audioDragging ? ' drag-over' : ''}`}
          onDragOver={(e: DragEvent) => { e.preventDefault(); setAudioDragging(true) }}
          onDragEnter={(e: DragEvent) => { e.preventDefault(); setAudioDragging(true) }}
          onDragLeave={() => setAudioDragging(false)}
          onDrop={(e: DragEvent) => {
            e.preventDefault()
            setAudioDragging(false)
            const file = e.dataTransfer.files[0]
            if (file) applyAudioFile(file)
          }}
        >
          <label className="file-pick-btn" htmlFor="audio-input">
            <span>FILE</span> Выбрать файл
          </label>
          <p className="file-name">{audioFile ? audioFile.name : 'Файл не выбран или перетащи сюда'}</p>
          {audioFile && audioDuration !== null && (
            <p className="file-meta">{fmtDuration(audioDuration)}</p>
          )}
        </div>
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
            onClick={() => {
              hapticSelection()
              setShowLyricsEditor(true)
            }}
          >
            {lyrics
              ? 'Текст добавлен (изменить)'
              : 'Добавить текст / таймкоды'}
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

      <div className="form-group">
        <label className="form-group-row">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
          />
          <span>
            Я подтверждаю, что обладаю правами на загружаемый контент
            и согласен с
            {' '}
            <a href="/legal/terms" target="_blank" rel="noreferrer">
              пользовательским соглашением
            </a>
            ,{' '}
            <a href="/legal/upload-rules" target="_blank" rel="noreferrer">
              правилами загрузки
            </a>
            {' '}и{' '}
            <a href="/legal/privacy" target="_blank" rel="noreferrer">
              политикой обработки данных
            </a>
            .
          </span>
        </label>
      </div>

      {error && <div className="form-error">{error}</div>}

      <button type="submit" className="btn-primary" disabled={uploading}>
        Загрузить
      </button>

      {uploading && (
        <div>
          <div className="progress-bar-wrap">
            <div
              className={`progress-bar-fill${uploadDone ? '' : ' shimmer'}`}
              style={{ width: uploadDone ? '100%' : undefined }}
            />
          </div>
          <p className="progress-label">
            {uploadDone ? 'Обработка…' : 'Загружаем файл…'}
          </p>
        </div>
      )}
    </form>
  )
}
