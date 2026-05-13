import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { MotionPress } from '@/components/ui/MotionPress'
import { coverProxyUrl } from '@/lib/coverProxy'
import { api } from '@/lib/api'

type EditContext = Awaited<
  ReturnType<typeof api.getTrackEditContext>
>

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

interface DraftFields {
  title: string
  artist: string
  genre: string
  description: string
  is_public: boolean
}

const DEBOUNCE_MS = 600
const DRAFT_TTL_MS = 24 * 60 * 60 * 1000

function draftKey(trackId: number): string {
  return `dotsound:edit-draft:${trackId}`
}

interface PersistedDraft {
  v: 1
  savedAt: number
  fields: DraftFields
}

function loadDraft(trackId: number): DraftFields | null {
  try {
    const raw = window.localStorage.getItem(draftKey(trackId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedDraft
    if (parsed.v !== 1) return null
    if (Date.now() - parsed.savedAt > DRAFT_TTL_MS) {
      window.localStorage.removeItem(draftKey(trackId))
      return null
    }
    return parsed.fields
  } catch {
    return null
  }
}

function saveDraft(trackId: number, fields: DraftFields): void {
  try {
    const payload: PersistedDraft = {
      v: 1,
      savedAt: Date.now(),
      fields,
    }
    window.localStorage.setItem(
      draftKey(trackId),
      JSON.stringify(payload),
    )
  } catch {
    /* quota / private mode — ignore */
  }
}

function clearDraft(trackId: number): void {
  try {
    window.localStorage.removeItem(draftKey(trackId))
  } catch {
    /* ignore */
  }
}

function contextToFields(ctx: EditContext): DraftFields {
  return {
    title: ctx.title ?? '',
    artist: ctx.artist ?? '',
    genre: ctx.genre ?? '',
    description: ctx.description ?? '',
    is_public: ctx.is_public,
  }
}

export function TrackEditView() {
  const { trackId: trackIdParam } = useParams<{ trackId: string }>()
  const trackId = trackIdParam ? Number(trackIdParam) : NaN
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [ctx, setCtx] = useState<EditContext | null>(null)
  const [fields, setFields] = useState<DraftFields | null>(null)
  const [serverFields, setServerFields] =
    useState<DraftFields | null>(null)
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const coverInputRef = useRef<HTMLInputElement | null>(null)

  const isProcessing = ctx?.is_processing ?? false

  useEffect(() => {
    if (Number.isNaN(trackId) || trackId <= 0) {
      navigate('/', { replace: true })
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const res = await api.getTrackEditContext(trackId)
        if (cancelled) return
        setCtx(res)
        const draft = loadDraft(trackId)
        const base = contextToFields(res)
        setServerFields(base)
        setFields(draft ?? base)
        if (res.cover_key) {
          setCoverPreview(coverProxyUrl(res.cover_key))
        }
      } catch (err) {
        if (cancelled) return
        setError(
          err instanceof Error
            ? err.message
            : 'Не удалось загрузить трек',
        )
      }
    })()
    return () => {
      cancelled = true
    }
  }, [trackId, navigate])

  const dirtyDiff = useMemo(() => {
    if (!fields || !serverFields) return null
    const diff: Partial<DraftFields> = {}
    if (fields.title !== serverFields.title)
      diff.title = fields.title
    if (fields.artist !== serverFields.artist)
      diff.artist = fields.artist
    if (fields.genre !== serverFields.genre)
      diff.genre = fields.genre
    if (fields.description !== serverFields.description)
      diff.description = fields.description
    if (fields.is_public !== serverFields.is_public)
      diff.is_public = fields.is_public
    return Object.keys(diff).length ? diff : null
  }, [fields, serverFields])

  const flushSave = useCallback(
    async (diff: Partial<DraftFields>) => {
      if (!fields) return
      setSaveState('saving')
      try {
        await api.updateTrack(trackId, {
          title: diff.title,
          artist:
            diff.artist === '' ? null : diff.artist,
          genre: diff.genre === '' ? null : diff.genre,
          description:
            diff.description === '' ? null : diff.description,
          is_public: diff.is_public,
        })
        setServerFields(fields)
        setSaveState('saved')
        clearDraft(trackId)
        setTimeout(() => setSaveState('idle'), 1500)
      } catch (err) {
        setSaveState('error')
        setError(
          err instanceof Error
            ? err.message
            : 'Не удалось сохранить',
        )
      }
    },
    [fields, trackId],
  )

  useEffect(() => {
    if (!fields || !serverFields) return
    saveDraft(trackId, fields)
    if (!dirtyDiff) return
    const timer = window.setTimeout(() => {
      void flushSave(dirtyDiff)
    }, DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [fields, serverFields, dirtyDiff, flushSave, trackId])

  const setField = <K extends keyof DraftFields>(
    key: K,
    value: DraftFields[K],
  ): void => {
    setFields((prev) =>
      prev ? { ...prev, [key]: value } : prev,
    )
  }

  const handleCoverPick = async (file: File) => {
    if (!file) return
    const url = URL.createObjectURL(file)
    setCoverPreview(url)
    setBusy(true)
    try {
      const form = new FormData()
      form.append('cover', file)
      await api.uploadTrackCover(trackId, form)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить обложку',
      )
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    return () => {
      if (coverPreview && coverPreview.startsWith('blob:')) {
        URL.revokeObjectURL(coverPreview)
      }
    }
  }, [coverPreview])

  const handleDelete = async () => {
    if (
      !window.confirm(
        t(
          'trackEdit.confirmDelete',
          'Удалить трек? Его можно восстановить из корзины.',
        ),
      )
    ) {
      return
    }
    setBusy(true)
    try {
      await api.deleteTrack(trackId)
      clearDraft(trackId)
      navigate('/library', { replace: true })
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось удалить',
      )
      setBusy(false)
    }
  }

  if (Number.isNaN(trackId) || trackId <= 0) return null

  if (!ctx || !fields) {
    return (
      <div className="page-loading">
        {error
          ? error
          : t('common.loading', 'Загрузка…')}
      </div>
    )
  }

  const titleLen = fields.title.length
  const titleNear = titleLen > 256 - 20
  const titleOver = titleLen > 256

  return (
    <div className="track-edit-view">
      <header className="te-header">
        <MotionPress
          type="button"
          variant="ghost"
          onClick={() => navigate(-1)}
          aria-label={t('common.back', 'Назад')}
        >
          ←
        </MotionPress>
        <h1 className="te-title">
          {t('trackEdit.title', 'Редактирование трека')}
        </h1>
        <span
          className={`te-save te-save--${saveState}`}
          aria-live="polite"
        >
          {saveState === 'saving' &&
            t('trackEdit.saving', 'Сохраняем…')}
          {saveState === 'saved' &&
            t('trackEdit.saved', 'Сохранено')}
          {saveState === 'error' &&
            t('trackEdit.saveError', 'Ошибка сохранения')}
        </span>
      </header>

      {isProcessing ? (
        <div className="te-banner te-banner--info">
          {t(
            'trackEdit.processingNote',
            'Трек ещё обрабатывается — некоторые поля могут обновиться автоматически.',
          )}
        </div>
      ) : null}

      <section className="te-section" aria-labelledby="te-sec-meta">
        <h2 id="te-sec-meta">
          {t('trackEdit.sectionMeta', 'Метаданные')}
        </h2>
        <label className="te-field">
          <span>{t('trackEdit.titleField', 'Название')}</span>
          <input
            type="text"
            value={fields.title}
            maxLength={300}
            onChange={(e) => setField('title', e.target.value)}
            aria-invalid={titleOver}
          />
          <span
            className={`te-counter ${
              titleOver
                ? 'te-counter--over'
                : titleNear
                  ? 'te-counter--near'
                  : ''
            }`}
          >
            {titleLen}/256
          </span>
        </label>
        <label className="te-field">
          <span>{t('trackEdit.artistField', 'Артист')}</span>
          <input
            type="text"
            value={fields.artist}
            maxLength={256}
            onChange={(e) => setField('artist', e.target.value)}
            disabled={!ctx.can_edit_artist}
          />
        </label>
        <label className="te-field">
          <span>{t('trackEdit.genreField', 'Жанр')}</span>
          <input
            type="text"
            value={fields.genre}
            maxLength={100}
            onChange={(e) => setField('genre', e.target.value)}
          />
        </label>
        <label className="te-field">
          <span>{t('trackEdit.descField', 'Описание')}</span>
          <textarea
            value={fields.description}
            maxLength={2000}
            rows={4}
            onChange={(e) =>
              setField('description', e.target.value)
            }
          />
          <span className="te-counter">
            {fields.description.length}/2000
          </span>
        </label>
      </section>

      <section className="te-section" aria-labelledby="te-sec-cover">
        <h2 id="te-sec-cover">
          {t('trackEdit.sectionCover', 'Обложка')}
        </h2>
        <div className="te-cover-row">
          <div className="te-cover-preview">
            {coverPreview ? (
              <img
                src={coverPreview}
                alt=""
                width={160}
                height={160}
              />
            ) : (
              <div className="te-cover-empty" />
            )}
          </div>
          <div className="te-cover-actions">
            <input
              ref={coverInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void handleCoverPick(f)
              }}
            />
            <MotionPress
              type="button"
              variant="primary"
              disabled={busy}
              onClick={() => coverInputRef.current?.click()}
            >
              {t('trackEdit.uploadCover', 'Загрузить обложку')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  await api.regenerateTrackCover(trackId)
                } catch (err) {
                  setError(
                    err instanceof Error ? err.message : 'Ошибка',
                  )
                } finally {
                  setBusy(false)
                }
              }}
            >
              {t('trackEdit.regenerateCover', 'Сгенерировать заново')}
            </MotionPress>
          </div>
        </div>
      </section>

      <section
        className="te-section"
        aria-labelledby="te-sec-lyrics"
      >
        <h2 id="te-sec-lyrics">
          {t('trackEdit.sectionLyrics', 'Текст и таймкоды')}
        </h2>
        <p className="te-hint">
          {ctx.has_lyrics
            ? t(
                'trackEdit.lyricsPresent',
                'Текст уже добавлен. Открой карточку трека, чтобы отредактировать таймкоды.',
              )
            : t(
                'trackEdit.lyricsAbsent',
                'У трека пока нет текста. Открой карточку, чтобы добавить.',
              )}
        </p>
        <MotionPress
          type="button"
          variant="primary"
          onClick={() => navigate(`/?openTrack=${trackId}&lyrics=1`)}
        >
          {t('trackEdit.openLyricsEditor', 'Открыть редактор лирики')}
        </MotionPress>
      </section>

      <section
        className="te-section"
        aria-labelledby="te-sec-vis"
      >
        <h2 id="te-sec-vis">
          {t('trackEdit.sectionVisibility', 'Видимость')}
        </h2>
        <label className="te-toggle">
          <input
            type="checkbox"
            checked={fields.is_public}
            onChange={(e) =>
              setField('is_public', e.target.checked)
            }
          />
          <span>
            {t(
              'trackEdit.isPublicLabel',
              'Трек виден всем пользователям',
            )}
          </span>
        </label>
      </section>

      {ctx.can_delete ? (
        <section
          className="te-section te-section--danger"
          aria-labelledby="te-sec-danger"
        >
          <h2 id="te-sec-danger">
            {t('trackEdit.sectionDanger', 'Опасная зона')}
          </h2>
          <p className="te-hint">
            {t(
              'trackEdit.dangerHint',
              'Удалённый трек попадает в корзину и может быть восстановлен в течение grace-периода.',
            )}
          </p>
          <MotionPress
            type="button"
            variant="danger"
            disabled={busy}
            onClick={handleDelete}
          >
            {t('trackEdit.deleteTrack', 'Удалить трек')}
          </MotionPress>
        </section>
      ) : null}

      {error ? (
        <div className="te-banner te-banner--error" role="alert">
          {error}
        </div>
      ) : null}
    </div>
  )
}

export default TrackEditView
