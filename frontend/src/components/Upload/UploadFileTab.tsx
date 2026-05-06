import {
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence } from 'framer-motion'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { dismissIsland, showIsland } from '@/lib/island'
import { getInternalUserId } from '@/lib/telegram'
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

export function UploadFileTab({ onSuccess }: Props) {
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [artistMode, setArtistMode] = useState<'profile' | 'custom'>('custom')
  const [profileArtistName, setProfileArtistName] = useState<string | null>(null)
  const [artistQuery, setArtistQuery] = useState('')
  const [artistOpen, setArtistOpen] = useState(false)
  const [artistSearching, setArtistSearching] = useState(false)
  const [artistResults, setArtistResults] = useState<string[]>([])
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
  const [coverDragging, setCoverDragging] =
    useState(false)
  const [audioDragging, setAudioDragging] =
    useState(false)
  const [wizardStep, setWizardStep] = useState(0)

  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const transition = reduce ? TWEEN_FAST : SPRING_GENTLE

  useEffect(() => {
    api.getGenres().then(setGenres).catch(() => {})
  }, [])

  useEffect(() => {
    const userId = getInternalUserId()
    if (!userId) {
      return
    }
    api.getUserProfile(userId)
      .then((user) => {
        const display = user.display_name?.trim() ?? ''
        if (!display) {
          setProfileArtistName(null)
          setArtistMode('custom')
          return
        }
        setProfileArtistName(display)
        setArtist(display)
        setArtistQuery(display)
        setArtistMode('profile')
      })
      .catch(() => {})
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
    const query = artistQuery.trim()
    if (!artistOpen || !query) {
      setArtistResults([])
      setArtistSearching(false)
      return
    }

    let cancelled = false
    const timer = window.setTimeout(() => {
      setArtistSearching(true)
      void (async () => {
        const artistsFromApi = await api
          .getArtists(query, 12)
          .catch(() => ({ items: [] as { name: string }[] }))
        const trackHits = await api
          .getTracks({ q: query, size: 30 })
          .catch(() => ({ items: [] as Track[] }))
        const merged = [
          ...artistsFromApi.items.map((x) => x.name.trim()),
          ...trackHits.items
            .map((t) => t.artist?.trim() ?? '')
            .filter((x) => x.length > 0),
        ]
        const seen = new Set<string>()
        const result: string[] = []
        for (const item of merged) {
          const key = item.toLowerCase()
          if (seen.has(key)) {
            continue
          }
          seen.add(key)
          result.push(item)
          if (result.length >= 10) {
            break
          }
        }
        if (!cancelled) {
          setArtistResults(result)
          setArtistSearching(false)
        }
      })()
    }, 220)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [artistOpen, artistQuery])

  const hasExactArtist = useMemo(
    () => artistResults.some(
      (value) => value.toLowerCase() === artistQuery.trim().toLowerCase(),
    ),
    [artistResults, artistQuery],
  )

  useEffect(() => {
    return () => {
      if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
    }
  }, [localAudioUrl])

  const applyAudioFile = (file: File) => {
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
    setArtistMode(profileArtistName ? 'profile' : 'custom')
    setArtistQuery('')
    setArtistOpen(false)
    setArtistSearching(false)
    setArtistResults([])
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
    setWizardStep(0)
  }

  function syncGenreArtistDraft() {
    if (genreQuery.trim()) {
      const exact = normalizedGenres.get(
        genreQuery.trim().toLowerCase(),
      )
      setGenre(exact ?? genreQuery.trim())
    }
    if (artistMode === 'custom' && artistQuery.trim()) {
      setArtist(artistQuery.trim())
    }
    if (
      artistMode === 'profile' &&
      profileArtistName?.trim()
    ) {
      setArtist(profileArtistName.trim())
    }
  }

  function handleWizardNext() {
    setError('')
    if (wizardStep === 0) {
      if (!audioFile) {
        setError('Выберите аудиофайл')
        return
      }
      setWizardStep(1)
      return
    }
    if (wizardStep === 1) {
      syncGenreArtistDraft()
      if (!title.trim()) {
        setError('Введите название трека')
        return
      }
      if (
        artistMode === 'profile' &&
        !profileArtistName?.trim()
      ) {
        setError(
          'Укажи display name в профиле для режима "Я артист"',
        )
        return
      }
      setWizardStep(2)
      return
    }
    if (wizardStep === 2) {
      setWizardStep(3)
    }
  }

  function handleWizardBack() {
    if (!uploading && wizardStep > 0) {
      setWizardStep((s) => Math.max(0, s - 1))
    }
  }

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault()
    setError('')
    syncGenreArtistDraft()
    if (artistMode === 'profile') {
      if (!profileArtistName?.trim()) {
        setError(
          'Укажи display name в профиле для режима "Я артист"',
        )
        return
      }
      setArtist(profileArtistName.trim())
    }

    if (!title.trim()) {
      setError('Введите название трека')
      return
    }
    if (!audioFile) {
      setError('Выберите аудиофайл')
      return
    }
    if (!termsAccepted) {
      setError(
        'Подтвердите права на контент и согласие с условиями загрузки',
      )
      return
    }

    setUploading(true)
    setUploadDone(false)

    let islandId: string | undefined
    try {
      islandId = showIsland({
        kind: 'progress',
        title: t('redesign.upload.progressTitle'),
        hint: t('redesign.upload.progressHint'),
      })
      const fd = new FormData()
      fd.append('file', audioFile)
      fd.append('title', title.trim())
      if (artist.trim()) fd.append('artist', artist.trim())
      fd.append(
        'use_profile_artist',
        artistMode === 'profile' ? 'true' : 'false',
      )
      if (genre.trim()) fd.append('genre', genre.trim())
      if (coverFile) fd.append('cover', coverFile)
      fd.append('is_public', String(isPublic))
      fd.append('upload_terms_accepted', 'true')

      const uploaded = await api.uploadTrack(fd)

      if (lyrics) {
        if (lyrics.synced_lines) {
          await api.saveLyricsSync(
            uploaded.id,
            lyrics.synced_lines,
          )
        } else {
          await api.saveLyrics(
            uploaded.id,
            lyrics.plain_text,
          )
        }
      }
      setUploadDone(true)
      if (islandId) dismissIsland(islandId)
      showIsland({
        kind: 'toast',
        title: t('redesign.upload.doneToast'),
        durationMs: 2800,
      })
      hapticNotification('success')

      setTimeout(async () => {
        const fullTrack = await api.getTrack(uploaded.id)
        reset()
        onSuccess(fullTrack)
      }, 600)
    } catch (err: unknown) {
      if (islandId) dismissIsland(islandId)
      setUploading(false)
      setUploadDone(false)
      const msg = err instanceof Error ? err.message : ''
      setError(
        msg === '415'
          ? 'Формат файла не поддерживается'
          : msg === '413'
            ? 'Файл слишком большой (макс. 50 МБ)'
            : 'Ошибка загрузки. Попробуй ещё раз.',
      )
      hapticNotification('error')
    }
  }

  const wizardHints = [
    ['wizardAudioTitle', 'wizardAudioHint'],
    ['wizardDetailsTitle', 'wizardDetailsHint'],
    ['wizardCoverTitle', 'wizardCoverHint'],
    ['wizardPreviewTitle', 'wizardPreviewHint'],
  ] as const

  const draftArtistLabel =
    artistMode === 'profile'
      ? profileArtistName?.trim() || artist.trim()
      : artist.trim()

  return (
    <form id="upload-form" noValidate onSubmit={handleSubmit}>
      <div className="ru-up-wizard-head">
        <h3>
          {t(
            `redesign.upload.${wizardHints[wizardStep][0]}`,
          )}
        </h3>
        <p>
          {t(
            `redesign.upload.${wizardHints[wizardStep][1]}`,
          )}
        </p>
      </div>
      <div className="ru-up-step-dots" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={
              i === wizardStep
                ? 'ru-up-step-dot is-active'
                : 'ru-up-step-dot'
            }
          />
        ))}
      </div>

      <AnimatePresence mode="wait">
        <m.div
          key={wizardStep}
          initial={
            reduce ? false : { opacity: 0, y: 12 }
          }
          animate={{ opacity: 1, y: 0 }}
          exit={
            reduce ? undefined : { opacity: 0, y: -10 }
          }
          transition={transition}
        >
          {wizardStep === 0 && (
            <div className="form-group">
              <label className="form-label">
                Аудиофайл *
              </label>
              <div
                className={`audio-drop-zone${audioDragging ? ' drag-over' : ''}`}
                onDragOver={(e: DragEvent) => {
                  e.preventDefault()
                  setAudioDragging(true)
                }}
                onDragEnter={(e: DragEvent) => {
                  e.preventDefault()
                  setAudioDragging(true)
                }}
                onDragLeave={() => setAudioDragging(false)}
                onDrop={(e: DragEvent) => {
                  e.preventDefault()
                  setAudioDragging(false)
                  const file = e.dataTransfer.files[0]
                  if (file) applyAudioFile(file)
                }}
              >
                <label
                  className="file-pick-btn"
                  htmlFor="audio-input"
                >
                  <span>FILE</span> Выбрать файл
                </label>
                <p className="file-name">
                  {audioFile
                    ? audioFile.name
                    : 'Файл не выбран или перетащи сюда'}
                </p>
                {audioFile && audioDuration !== null && (
                  <p className="file-meta">
                    {fmtDuration(audioDuration)}
                  </p>
                )}
              </div>
              <input
                id="audio-input"
                type="file"
                accept="audio/*"
                hidden
                onChange={handleAudioChange}
              />
            </div>
          )}

          {wizardStep === 1 && (
            <>
              <div className="form-group">
                <label
                  className="form-label"
                  htmlFor="title-input"
                >
                  Название *
                </label>
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

              <div className="form-group genre-search-group">
                <label className="form-label">
                  Исполнитель
                </label>
                <div className="upload-artist-mode">
                  <button
                    type="button"
                    className={`upload-artist-mode-btn${artistMode === 'profile' ? ' active' : ''}`}
                    onClick={() => {
                      if (!profileArtistName) {
                        hapticNotification('warning')
                        return
                      }
                      setArtistMode('profile')
                      setArtist(profileArtistName)
                      setArtistQuery(profileArtistName)
                      setArtistOpen(false)
                      hapticSelection()
                    }}
                  >
                    Я этот артист
                  </button>
                  <button
                    type="button"
                    className={`upload-artist-mode-btn${artistMode === 'custom' ? ' active' : ''}`}
                    onClick={() => {
                      setArtistMode('custom')
                      hapticSelection()
                    }}
                  >
                    Ввести вручную
                  </button>
                </div>
                {artistMode === 'profile' && (
                  <p className="upload-artist-profile-note">
                    {profileArtistName
                      ? `Будет использовано имя профиля: ${profileArtistName}`
                      : 'Добавь display name в профиле, чтобы использовать этот режим.'}
                  </p>
                )}
                {artistMode === 'custom' && (
                  <>
                    <button
                      type="button"
                      className="genre-search-toggle"
                      onClick={() => {
                        setArtistOpen((prev) => !prev)
                        hapticSelection()
                      }}
                    >
                      <Icon name="search" size={16} />
                      <span>
                        {artist || 'Поиск исполнителя'}
                      </span>
                      <Icon
                        name={
                          artistOpen ? 'chevron-up' : 'chevron-down'
                        }
                        size={16}
                      />
                    </button>
                    {artistOpen && (
                      <div
                        className="genre-search-popover"
                        role="listbox"
                      >
                        <input
                          className="form-input genre-search-input"
                          placeholder="Начни вводить имя исполнителя"
                          maxLength={256}
                          value={artistQuery}
                          onChange={(e) => {
                            const next = e.target.value
                            setArtistQuery(next)
                            if (next.trim()) {
                              setArtist(next.trim())
                            }
                          }}
                        />
                        {artistSearching && (
                          <p className="genre-search-note">
                            Ищем похожих исполнителей…
                          </p>
                        )}
                        {!artistSearching &&
                          artistResults.length > 0 && (
                            <div className="genre-search-list">
                              {artistResults.map((item) => (
                                <button
                                  key={item}
                                  type="button"
                                  className={`genre-search-item${
                                    artist.toLowerCase() ===
                                    item.toLowerCase()
                                      ? ' active'
                                      : ''
                                  }`}
                                  onClick={() => {
                                    setArtist(item)
                                    setArtistQuery(item)
                                    setArtistOpen(false)
                                    hapticSelection()
                                  }}
                                >
                                  {item}
                                </button>
                              ))}
                            </div>
                          )}
                        {!artistSearching &&
                          artistQuery.trim() &&
                          !hasExactArtist && (
                            <button
                              type="button"
                              className="genre-search-create"
                              onClick={() => {
                                const custom =
                                  artistQuery.trim()
                                setArtist(custom)
                                setArtistQuery(custom)
                                setArtistOpen(false)
                                haptic('medium')
                              }}
                            >
                              Создать исполнителя:{' '}
                              {artistQuery.trim()}
                            </button>
                          )}
                        {!artistSearching &&
                          artistResults.length === 0 &&
                          !artistQuery.trim() && (
                            <p className="genre-search-note">
                              Подсказки появятся после ввода.
                            </p>
                          )}
                      </div>
                    )}
                  </>
                )}
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
                  <Icon
                    name={
                      genreOpen ? 'chevron-up' : 'chevron-down'
                    }
                    size={16}
                  />
                </button>
                {genreOpen && (
                  <div
                    className="genre-search-popover"
                    role="listbox"
                  >
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
                      <p className="genre-search-note">
                        Ищем похожие жанры…
                      </p>
                    )}
                    {!genreSearching &&
                      genreResults.length > 0 && (
                        <div className="genre-search-list">
                          {genreResults.map((item) => (
                            <button
                              key={item}
                              type="button"
                              className={`genre-search-item${
                                genre.toLowerCase() ===
                                item.toLowerCase()
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
                    {!genreSearching &&
                      genreQuery.trim() &&
                      !hasExactGenre && (
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
                    {!genreSearching &&
                      genreResults.length === 0 &&
                      !genreQuery.trim() && (
                        <p className="genre-search-note">
                          Популярные жанры появятся после ввода.
                        </p>
                      )}
                  </div>
                )}
              </div>

              {audioFile && (
                <div className="form-group">
                  <label className="form-label">
                    Текст песни
                  </label>
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

              <div className="form-group upload-checks">
                <label className="upload-check-row">
                  <input
                    type="checkbox"
                    checked={isPublic}
                    onChange={(e) =>
                      setIsPublic(e.target.checked)
                    }
                  />
                  <span>Публичный трек</span>
                </label>
                <label className="upload-check-row">
                  <input
                    type="checkbox"
                    checked={termsAccepted}
                    onChange={(e) =>
                      setTermsAccepted(e.target.checked)
                    }
                  />
                  <span>
                    Ознакомлен с{' '}
                    <a
                      href="/legal/upload-rules"
                      target="_blank"
                      rel="noreferrer"
                    >
                      правилами загрузки
                    </a>
                    .
                  </span>
                </label>
              </div>
            </>
          )}

          {wizardStep === 2 && (
            <>
              <label
                className={`cover-picker${coverDragging ? ' drag-over' : ''}`}
                htmlFor="cover-input"
                onDragOver={(e) => {
                  e.preventDefault()
                  setCoverDragging(true)
                }}
                onDragEnter={(e) => {
                  e.preventDefault()
                  setCoverDragging(true)
                }}
                onDragLeave={() => setCoverDragging(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setCoverDragging(false)
                  const file = e.dataTransfer.files[0]
                  if (file) applyCoverFile(file)
                }}
              >
                <div className="cover-preview">
                  {coverPreview ? (
                    <img src={coverPreview} alt="cover" />
                  ) : (
                    <span className="cover-placeholder">
                      Track
                    </span>
                  )}
                </div>
                <span className="cover-label">
                  Добавить обложку
                </span>
              </label>
              <input
                id="cover-input"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                hidden
                onChange={handleCoverChange}
              />
            </>
          )}

          {wizardStep === 3 && (
            <div className="ru-up-preview-stage">
              <AmbientStage coverUrl={coverPreview}>
                <div className="ru-up-preview-stage__inner">
                  <div className="ru-up-preview-cover-wrap">
                    {coverPreview ? (
                      <KenBurnsCover
                        src={coverPreview}
                        alt={t(
                          'redesign.upload.ambientAlt',
                        )}
                      />
                    ) : (
                      <div className="ru-up-preview-placeholder">
                        <Icon name="music" size={44} />
                      </div>
                    )}
                  </div>
                  <div className="ru-up-preview-meta">
                    <strong>
                      {title.trim() || '—'}
                    </strong>
                    <span>
                      {draftArtistLabel || '—'}
                    </span>
                    {audioDuration !== null && (
                      <span>
                        {fmtDuration(audioDuration)}
                      </span>
                    )}
                  </div>
                </div>
              </AmbientStage>
            </div>
          )}
        </m.div>
      </AnimatePresence>

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

      {error && <div className="form-error">{error}</div>}

      <div className="ru-up-wizard-nav">
        <div>
          {wizardStep > 0 && (
            <MotionPress
              type="button"
              variant="ghost"
              disabled={uploading}
              onClick={handleWizardBack}
            >
              {t('redesign.upload.wizardBack')}
            </MotionPress>
          )}
        </div>
        <div>
          {wizardStep < 3 ? (
            <MotionPress
              type="button"
              variant="primary"
              disabled={uploading}
              onClick={handleWizardNext}
            >
              {t('redesign.upload.wizardNext')}
            </MotionPress>
          ) : (
            <MotionPress
              type="submit"
              variant="primary"
              disabled={uploading}
            >
              {t('redesign.upload.wizardSubmit')}
            </MotionPress>
          )}
        </div>
      </div>

      {uploading && (
        <div>
          <div className="progress-bar-wrap">
            <div
              className={`progress-bar-fill${uploadDone ? '' : ' shimmer'}`}
              style={{
                width: uploadDone ? '100%' : undefined,
              }}
            />
          </div>
          <p className="progress-label">
            {uploadDone
              ? 'Обработка…'
              : 'Загружаем файл…'}
          </p>
        </div>
      )}
    </form>

  )
}
