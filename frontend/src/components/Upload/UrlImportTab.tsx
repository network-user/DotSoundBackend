import {
  useCallback,
  useState,
  type ChangeEvent,
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
import { Icon } from '@/components/Icon/Icon'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { dismissIsland, showIsland } from '@/lib/island'
import { getApiErrorMessage } from '@/lib/api'
import {
  hapticNotification,
  hapticSelection,
} from '@/lib/telegram'
import type { Track } from '@/types/api'

export interface UrlImportSource {
  id: string
  iconName: string
  placeholder: string
  importFn: (url: string, isPublic: boolean) => Promise<Track>
  errorKey: string
}

interface Props {
  source: UrlImportSource
  onSuccess: (track: Track) => void
}

function fmtDuration(sec?: number | null): string {
  if (!sec || sec <= 0) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export function UrlImportTab({ source, onSuccess }: Props) {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const [url, setUrl] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const [preview, setPreview] = useState<Track | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const transition = reduce ? TWEEN_FAST : SPRING_GENTLE

  const reset = useCallback(() => {
    setUrl('')
    setPreview(null)
    setError('')
  }, [])

  const handleUrlChange = (e: ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value)
    setPreview(null)
    setError('')
  }

  const resolveError = useCallback(
    (err: unknown): string => {
      const msg = err instanceof Error ? err.message : ''
      const isCode = /^[1-5]\d{2}$/.test(msg)
      const fallback = t(`redesign.upload.url.${source.errorKey}.def`, {
        defaultValue: t('redesign.upload.url.errorDefault'),
      })
      if (isCode) {
        return t(`redesign.upload.url.${source.errorKey}.${msg}`, {
          defaultValue: fallback,
        })
      }
      return getApiErrorMessage(err, fallback)
    },
    [source.errorKey, t],
  )

  const handlePreview = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!url.trim() || loading) return
    setError('')
    setPreview(null)
    setLoading(true)
    try {
      const track = await source.importFn(url.trim(), isPublic)
      setPreview(track)
      hapticSelection()
    } catch (err) {
      setError(resolveError(err))
      hapticNotification('error')
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    if (!preview) return
    const track = preview
    const id = showIsland({
      kind: 'toast',
      title: t('redesign.upload.url.addedToast'),
      durationMs: 2400,
    })
    hapticNotification('success')
    reset()
    onSuccess(track)
    window.setTimeout(() => dismissIsland(id), 2600)
  }

  return (
    <form
      className="ru-up-url"
      noValidate
      onSubmit={handlePreview}
    >
      <div className="ru-up-url__head">
        <span className="ru-up-url__icon">
          <Icon name={source.iconName} size={20} />
        </span>
        <div>
          <strong>
            {t(`redesign.upload.tab${source.id}`)}
          </strong>
          <p className="ru-up-url__hint">
            {t('redesign.upload.url.hint')}
          </p>
        </div>
      </div>

      <label className="ru-up-url__field">
        <span className="ru-up-url__label">
          {t('redesign.upload.url.linkLabel')}
        </span>
        <input
          className="ru-up-url__input"
          type="url"
          placeholder={source.placeholder}
          autoComplete="off"
          spellCheck={false}
          value={url}
          onChange={handleUrlChange}
          disabled={loading}
        />
      </label>

      <label className="ru-up-url__visibility">
        <input
          type="checkbox"
          checked={isPublic}
          onChange={(e) => setIsPublic(e.target.checked)}
          disabled={loading}
        />
        <span>{t('redesign.upload.url.publicLabel')}</span>
      </label>

      <div className="ru-up-url__actions">
        <MotionPress
          type="submit"
          variant="primary"
          disabled={loading || !url.trim()}
          haptic="selection"
        >
          {loading
            ? t('redesign.upload.url.fetching')
            : t('redesign.upload.url.fetch')}
        </MotionPress>
      </div>

      {error && (
        <m.div
          className="ru-up-url__error"
          initial={reduce ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition}
        >
          {error}
        </m.div>
      )}

      <AnimatePresence>
        {preview && (
          <m.div
            key={preview.id}
            className="ru-up-url__preview"
            initial={
              reduce ? false : { opacity: 0, y: 14, scale: 0.98 }
            }
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={
              reduce ? undefined : { opacity: 0, y: -8, scale: 0.98 }
            }
            transition={transition}
          >
            <div className="ru-up-url__preview-cover">
              {preview.cover_key ? (
                <KenBurnsCover
                  src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(preview.cover_key)}`}
                  alt={preview.title}
                />
              ) : (
                <div className="ru-up-url__preview-placeholder">
                  <Icon name="music" size={32} />
                </div>
              )}
            </div>
            <div className="ru-up-url__preview-meta">
              <strong>{preview.title}</strong>
              {preview.artist && (
                <span>{preview.artist}</span>
              )}
              {preview.duration_seconds ? (
                <span className="ru-up-url__preview-dur">
                  {fmtDuration(preview.duration_seconds)}
                </span>
              ) : null}
            </div>
            <div className="ru-up-url__preview-actions">
              <MotionPress
                type="button"
                variant="primary"
                onClick={handleAdd}
                haptic="medium"
              >
                {t('redesign.upload.url.addAndPlay')}
              </MotionPress>
              <MotionPress
                type="button"
                variant="ghost"
                onClick={reset}
                disabled={loading}
              >
                {t('redesign.upload.url.discard')}
              </MotionPress>
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </form>
  )
}
