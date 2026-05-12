import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  hasMeaningfulDraft,
  loadDraft,
  UPLOAD_DRAFT_CHANGED_EVENT,
  UPLOAD_DRAFT_STORAGE_KEY,
} from '@/lib/uploadDraft'
import { hapticSelection } from '@/lib/telegram'

function readHasMeaningfulDraft(): boolean {
  const d = loadDraft()
  return Boolean(d && hasMeaningfulDraft(d))
}

export function ProfileUploadCallout() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [expanded, setExpanded] = useState(false)
  const [hasDraft, setHasDraft] = useState(false)

  useEffect(() => {
    setHasDraft(readHasMeaningfulDraft())
  }, [location.pathname, location.key])

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === 'visible') {
        setHasDraft(readHasMeaningfulDraft())
      }
    }
    const onFocus = () => setHasDraft(readHasMeaningfulDraft())
    const onStorage = (ev: StorageEvent) => {
      if (ev.key === UPLOAD_DRAFT_STORAGE_KEY || ev.key === null) {
        setHasDraft(readHasMeaningfulDraft())
      }
    }
    const onDraftChanged = () => setHasDraft(readHasMeaningfulDraft())
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('focus', onFocus)
    window.addEventListener('storage', onStorage)
    window.addEventListener(UPLOAD_DRAFT_CHANGED_EVENT, onDraftChanged)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('storage', onStorage)
      window.removeEventListener(
        UPLOAD_DRAFT_CHANGED_EVENT,
        onDraftChanged,
      )
    }
  }, [])

  useEffect(() => {
    if (!expanded) {
      return
    }
    setHasDraft(readHasMeaningfulDraft())
  }, [expanded])

  const chevron = useMemo(
    () => (expanded ? 'chevron-up' : 'chevron-down'),
    [expanded],
  )

  const goUpload = () => {
    hapticSelection()
    navigate('/upload')
  }

  const goContinueDraft = () => {
    hapticSelection()
    navigate('/upload', { state: { applyDraft: true } })
  }

  return (
    <section
      className="profile-upload-callout"
      aria-label={t('profile.uploadCallout.title')}
    >
      <button
        type="button"
        className="profile-upload-callout__header"
        aria-expanded={expanded}
        onClick={() => {
          hapticSelection()
          setExpanded((v) => !v)
        }}
      >
        <span className="profile-upload-callout__icon" aria-hidden>
          <Icon name="upload" size={20} />
        </span>
        <span className="profile-upload-callout__title">
          {t('profile.uploadCallout.title')}
        </span>
        <span className="profile-upload-callout__chevron" aria-hidden>
          <Icon name={chevron} size={18} />
        </span>
      </button>
      {expanded && (
        <div className="profile-upload-callout__body">
          <p className="profile-upload-callout__text">
            {t('profile.uploadCallout.body')}
          </p>
          <div className="profile-upload-callout__actions">
            <MotionPress
              type="button"
              variant="primary"
              haptic="selection"
              onClick={goUpload}
            >
              {t('profile.uploadCallout.ctaUpload')}
            </MotionPress>
            {hasDraft && (
              <MotionPress
                type="button"
                variant="ghost"
                haptic="selection"
                onClick={goContinueDraft}
              >
                {t('profile.uploadCallout.ctaContinueDraft')}
              </MotionPress>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
