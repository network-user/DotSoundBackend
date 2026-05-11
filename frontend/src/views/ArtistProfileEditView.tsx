import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'

type StatusResponse = Awaited<ReturnType<typeof api.getMyArtist>>
type ArtistFields = NonNullable<StatusResponse['artist']>

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

interface DraftFields {
  bio: string
  country: string
  birth_date: string
  birthplace: string
  website_url: string
}

const DEBOUNCE_MS = 600
const DRAFT_TTL_MS = 24 * 60 * 60 * 1000
const DRAFT_KEY = 'dotsound:artist-edit-draft:v1'

interface PersistedDraft {
  v: 1
  savedAt: number
  fields: DraftFields
}

function loadDraft(): DraftFields | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedDraft
    if (parsed.v !== 1) return null
    if (Date.now() - parsed.savedAt > DRAFT_TTL_MS) {
      window.localStorage.removeItem(DRAFT_KEY)
      return null
    }
    return parsed.fields
  } catch {
    return null
  }
}

function saveDraft(fields: DraftFields): void {
  try {
    const payload: PersistedDraft = {
      v: 1,
      savedAt: Date.now(),
      fields,
    }
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(payload))
  } catch {
    /* ignore quota */
  }
}

function clearDraft(): void {
  try {
    window.localStorage.removeItem(DRAFT_KEY)
  } catch {
    /* ignore */
  }
}

function artistToFields(a: ArtistFields | null): DraftFields {
  return {
    bio: a?.bio ?? '',
    country: a?.country ?? '',
    birth_date: a?.birth_date ?? '',
    birthplace: a?.birthplace ?? '',
    website_url: a?.website_url ?? '',
  }
}

function completionPercent(
  fields: DraftFields,
  hasAvatar: boolean,
): number {
  const checks = [
    hasAvatar,
    fields.bio.trim().length >= 20,
    !!fields.country.trim(),
    !!fields.birth_date.trim(),
    !!fields.birthplace.trim(),
    !!fields.website_url.trim(),
  ]
  const filled = checks.filter(Boolean).length
  return Math.round((filled / checks.length) * 100)
}

function fieldsToPatch(
  fields: DraftFields,
  serverFields: DraftFields,
): Partial<DraftFields> {
  const patch: Partial<DraftFields> = {}
  ;(Object.keys(fields) as (keyof DraftFields)[]).forEach((k) => {
    if (fields[k] !== serverFields[k]) {
      patch[k] = fields[k]
    }
  })
  return patch
}

export function ArtistProfileEditView() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [fields, setFields] = useState<DraftFields | null>(null)
  const [serverFields, setServerFields] =
    useState<DraftFields | null>(null)
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [ensuring, setEnsuring] = useState(false)
  const [avatarPreview, setAvatarPreview] =
    useState<string | null>(null)
  const avatarInputRef = useRef<HTMLInputElement | null>(null)

  const refresh = useCallback(async () => {
    const res = await api.getMyArtist()
    setStatus(res)
    const base = artistToFields(res.artist)
    setServerFields(base)
    const draft = loadDraft()
    setFields(draft ?? base)
    if (res.artist?.image_key) {
      setAvatarPreview(
        `/api/v1/files/cover?key=${encodeURIComponent(res.artist.image_key)}`,
      )
    } else {
      setAvatarPreview(null)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await api.getMyArtist()
        if (cancelled) return
        setStatus(res)
        const base = artistToFields(res.artist)
        setServerFields(base)
        const draft = loadDraft()
        setFields(draft ?? base)
        if (res.artist?.image_key) {
          setAvatarPreview(
            `/api/v1/files/cover?key=${encodeURIComponent(res.artist.image_key)}`,
          )
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Не удалось загрузить профиль артиста',
          )
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const dirtyPatch = useMemo(() => {
    if (!fields || !serverFields) return null
    const patch = fieldsToPatch(fields, serverFields)
    return Object.keys(patch).length ? patch : null
  }, [fields, serverFields])

  const flushSave = useCallback(
    async (patch: Partial<DraftFields>) => {
      if (!fields) return
      setSaveState('saving')
      try {
        await api.updateMyArtist({
          bio:
            'bio' in patch
              ? (patch.bio?.trim() || null)
              : undefined,
          country:
            'country' in patch
              ? (patch.country?.trim() || null)
              : undefined,
          birth_date:
            'birth_date' in patch
              ? (patch.birth_date || null)
              : undefined,
          birthplace:
            'birthplace' in patch
              ? (patch.birthplace?.trim() || null)
              : undefined,
          website_url:
            'website_url' in patch
              ? (patch.website_url?.trim() || null)
              : undefined,
        })
        setServerFields(fields)
        setSaveState('saved')
        clearDraft()
        window.setTimeout(() => setSaveState('idle'), 1500)
      } catch (err) {
        setSaveState('error')
        setError(
          err instanceof Error
            ? err.message
            : 'Не удалось сохранить',
        )
      }
    },
    [fields],
  )

  useEffect(() => {
    if (!fields || !serverFields) return
    saveDraft(fields)
    if (!dirtyPatch) return
    const timer = window.setTimeout(() => {
      void flushSave(dirtyPatch)
    }, DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [fields, serverFields, dirtyPatch, flushSave])

  const setField = <K extends keyof DraftFields>(
    key: K,
    value: DraftFields[K],
  ): void => {
    setFields((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  const handleEnsure = async () => {
    setEnsuring(true)
    setError(null)
    try {
      await api.ensureMyArtist()
      await refresh()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось создать артиста',
      )
    } finally {
      setEnsuring(false)
    }
  }

  const handleAvatarPick = async (file: File) => {
    if (!file) return
    const localUrl = URL.createObjectURL(file)
    setAvatarPreview(localUrl)
    setBusy(true)
    try {
      const form = new FormData()
      form.append('avatar', file)
      await api.uploadMyArtistAvatar(form)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить аватар',
      )
    } finally {
      setBusy(false)
    }
  }

  if (!status) {
    return (
      <div className="page-loading">
        {error ? error : t('common.loading', 'Загрузка…')}
      </div>
    )
  }

  if (!status.has_artist) {
    const displayMissing = !status.display_name?.trim()
    return (
      <div className="artist-edit-view">
        <header className="te-header">
          <MotionPress
            type="button"
            variant="ghost"
            onClick={() => navigate(-1)}
          >
            ←
          </MotionPress>
          <h1 className="te-title">
            {t('artistEdit.title', 'Профиль артиста')}
          </h1>
        </header>
        <div className="te-section">
          <h2>
            {t(
              'artistEdit.becomeTitle',
              'Стать артистом на платформе',
            )}
          </h2>
          <p className="te-hint">
            {displayMissing
              ? t(
                  'artistEdit.becomeNeedName',
                  'Чтобы создать профиль артиста, сначала задайте имя в профиле — оно станет именем артиста.',
                )
              : t(
                  'artistEdit.becomeWithName',
                  'Имя артиста будет «{{name}}» — оно синхронизируется с твоим именем в профиле. После создания ты сможешь добавить аватар, био и другие поля.',
                  { name: status.display_name },
                )}
          </p>
          <div className="ae-cta-row">
            {displayMissing ? (
              <MotionPress
                type="button"
                variant="primary"
                onClick={() => navigate('/profile')}
              >
                {t('artistEdit.goSetName', 'Открыть профиль')}
              </MotionPress>
            ) : (
              <MotionPress
                type="button"
                variant="primary"
                disabled={ensuring}
                onClick={handleEnsure}
              >
                {ensuring
                  ? t('common.loading', 'Загрузка…')
                  : t(
                      'artistEdit.becomeAction',
                      'Создать профиль артиста',
                    )}
              </MotionPress>
            )}
          </div>
        </div>
        {error ? (
          <div className="te-banner te-banner--error">{error}</div>
        ) : null}
      </div>
    )
  }

  if (!fields) {
    return (
      <div className="page-loading">
        {t('common.loading', 'Загрузка…')}
      </div>
    )
  }

  const a = status.artist
  const bioLen = fields.bio.length
  const bioNear = bioLen > 2000 - 80
  const bioOver = bioLen > 2000

  return (
    <div className="artist-edit-view">
      <header className="te-header">
        <MotionPress
          type="button"
          variant="ghost"
          onClick={() => navigate(-1)}
        >
          ←
        </MotionPress>
        <h1 className="te-title">
          {t('artistEdit.title', 'Профиль артиста')}
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

      <section className="te-section ae-hero-section">
        <div className="ae-hero">
          <div
            className="ae-avatar"
            onClick={() => avatarInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                avatarInputRef.current?.click()
              }
            }}
          >
            {avatarPreview ? (
              <img src={avatarPreview} alt="" />
            ) : (
              <div className="ae-avatar__empty">
                {(a?.name || '?').slice(0, 1).toUpperCase()}
              </div>
            )}
            <div className="ae-avatar__overlay">
              {t('artistEdit.changeAvatar', 'Сменить')}
            </div>
          </div>
          <div className="ae-hero-meta">
            <div className="ae-hero-name">
              {a?.name ?? status.display_name}
            </div>
            <div className="ae-hero-hint">
              {t(
                'artistEdit.nameSyncHint',
                'Имя артиста синхронизируется с именем в профиле.',
              )}
            </div>
            <div
              className="ae-progress"
              role="progressbar"
              aria-label={t(
                'artistEdit.completionLabel',
                'Заполненность профиля',
              )}
              aria-valuenow={completionPercent(
                fields,
                Boolean(avatarPreview),
              )}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div className="ae-progress__track">
                <div
                  className="ae-progress__fill"
                  style={{
                    width: `${completionPercent(fields, Boolean(avatarPreview))}%`,
                  }}
                />
              </div>
              <span className="ae-progress__label">
                {t('artistEdit.completion', 'Заполнено {{pct}}%', {
                  pct: completionPercent(
                    fields,
                    Boolean(avatarPreview),
                  ),
                })}
              </span>
            </div>
          </div>
        </div>
        {avatarPreview ? (
          <div className="ae-avatar-actions">
            <MotionPress
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  await api.removeMyArtistAvatar()
                  setAvatarPreview(null)
                } catch (err) {
                  setError(
                    err instanceof Error
                      ? err.message
                      : 'Не удалось убрать аватар',
                  )
                } finally {
                  setBusy(false)
                }
              }}
            >
              {t('artistEdit.removeAvatar', 'Убрать аватар')}
            </MotionPress>
          </div>
        ) : null}
        <input
          ref={avatarInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void handleAvatarPick(f)
          }}
        />
      </section>

      <section className="te-section" aria-labelledby="ae-sec-bio">
        <h2 id="ae-sec-bio">{t('artistEdit.sectionBio', 'Био')}</h2>
        <label className="te-field">
          <span>
            {t('artistEdit.bioLabel', 'Расскажи о себе')}
          </span>
          <textarea
            value={fields.bio}
            maxLength={2200}
            rows={5}
            placeholder={t(
              'artistEdit.bioPlaceholder',
              'Жанр, история, влияния, проекты…',
            )}
            onChange={(e) => setField('bio', e.target.value)}
            aria-invalid={bioOver}
          />
          <span
            className={`te-counter ${
              bioOver
                ? 'te-counter--over'
                : bioNear
                  ? 'te-counter--near'
                  : ''
            }`}
          >
            {bioLen}/2000
          </span>
        </label>
      </section>

      <section
        className="te-section"
        aria-labelledby="ae-sec-where"
      >
        <h2 id="ae-sec-where">
          {t('artistEdit.sectionWhere', 'Откуда')}
        </h2>
        <label className="te-field">
          <span>
            {t(
              'artistEdit.countryLabel',
              'Страна (ISO-код, например RU)',
            )}
          </span>
          <input
            type="text"
            value={fields.country}
            maxLength={2}
            placeholder="RU"
            onChange={(e) =>
              setField('country', e.target.value.toUpperCase())
            }
          />
        </label>
        <label className="te-field">
          <span>{t('artistEdit.birthplaceLabel', 'Город')}</span>
          <input
            type="text"
            value={fields.birthplace}
            maxLength={128}
            onChange={(e) => setField('birthplace', e.target.value)}
          />
        </label>
        <label className="te-field">
          <span>
            {t('artistEdit.birthDateLabel', 'Дата рождения')}
          </span>
          <input
            type="date"
            value={fields.birth_date}
            onChange={(e) => setField('birth_date', e.target.value)}
          />
        </label>
      </section>

      <section className="te-section" aria-labelledby="ae-sec-web">
        <h2 id="ae-sec-web">
          {t('artistEdit.sectionWeb', 'Ссылки')}
        </h2>
        <label className="te-field">
          <span>{t('artistEdit.websiteLabel', 'Сайт')}</span>
          <input
            type="url"
            inputMode="url"
            placeholder="https://"
            value={fields.website_url}
            maxLength={512}
            onChange={(e) => setField('website_url', e.target.value)}
          />
        </label>
      </section>

      {error ? (
        <div className="te-banner te-banner--error">{error}</div>
      ) : null}
    </div>
  )
}

export default ArtistProfileEditView
