import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence } from 'framer-motion'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { hapticNotification, hapticSelection } from '@/lib/telegram'
import { usePlayerActions } from '@/store/PlayerContext'
import { UploadFileTab } from '@/components/Upload/UploadFileTab'
import { UploadQueueBadge } from '@/components/Upload/UploadQueueBadge'
import { UploadSoundCloudTab } from '@/components/Upload/UploadSoundCloudTab'
import { UploadBandcampTab } from '@/components/Upload/UploadBandcampTab'
import {
  clearDraft,
  hasMeaningfulDraft,
  loadDraft,
  type UploadDraft,
} from '@/lib/uploadDraft'
import type { Track } from '@/types/api'

import '@/styles/redesign-upload.css'
import '@/styles/redesign-track-edit.css'

type Tab = 'file' | 'soundcloud' | 'bandcamp'

type UploadLocationState = { applyDraft?: boolean }

export function UploadView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const reduce = useReducedMotion()
  const { playTrack } = usePlayerActions()
  const [tab, setTab] = useState<Tab>('file')
  const [pendingDraft, setPendingDraft] = useState<UploadDraft | null>(null)
  const [appliedDraft, setAppliedDraft] = useState<UploadDraft | null>(null)

  useEffect(() => {
    const draft = loadDraft()
    if (draft && hasMeaningfulDraft(draft)) {
      setPendingDraft(draft)
    }
  }, [])

  useEffect(() => {
    const st = location.state as UploadLocationState | null
    if (!st?.applyDraft) {
      return
    }
    const draft = loadDraft()
    if (draft && hasMeaningfulDraft(draft)) {
      setAppliedDraft(draft)
      setPendingDraft(null)
    }
    navigate(location.pathname, { replace: true, state: null })
  }, [location.pathname, location.state, navigate])

  const handleContinueDraft = () => {
    hapticSelection()
    setAppliedDraft(pendingDraft)
    setPendingDraft(null)
  }

  const handleDiscardDraft = () => {
    hapticSelection()
    clearDraft()
    setPendingDraft(null)
    setAppliedDraft(null)
  }

  const handleSuccess = async (track: Track) => {
    clearDraft()
    hapticNotification('success')
    navigate(`/track/${track.id}`)
    await playTrack(track)
  }

  const handleTabChange = (next: Tab) => {
    if (tab === next) {
      return
    }
    hapticSelection()
    setTab(next)
  }

  const transition = reduce ? TWEEN_FAST : SPRING_GENTLE

  return (
    <section
      id="view-upload"
      className="view active upload-view ru-up-root"
    >
      <div className="view-header upload-view__header ru-up-header">
        <div className="upload-view__header-row">
          <h2>{t('redesign.upload.screenTitle')}</h2>
          <UploadQueueBadge />
        </div>
        <p className="upload-view__subtitle ru-up-subtitle">
          {t('redesign.upload.screenSubtitle')}
        </p>
      </div>

      <div
        className="upload-tabs ru-up-tabs"
        role="tablist"
        aria-label={t('redesign.upload.screenTitle')}
      >
        {(
          [
            ['file', 'tabFile'],
            ['soundcloud', 'tabSoundCloud'],
            ['bandcamp', 'tabBandcamp'],
          ] as const
        ).map(([id, labelKey]) => (
          <MotionPress
            key={id}
            type="button"
            variant={tab === id ? 'primary' : 'ghost'}
            haptic="selection"
            aria-selected={tab === id}
            role="tab"
            className={
              tab === id ? 'ru-up-tab is-active' : 'ru-up-tab'
            }
            onClick={() => handleTabChange(id)}
          >
            {t(`redesign.upload.${labelKey}`)}
          </MotionPress>
        ))}
      </div>

      {pendingDraft && (
        <div className="ru-up-draft-banner" role="status">
          <div className="ru-up-draft-banner__text">
            <strong>{t('redesign.upload.draftBanner.title')}</strong>
            <p>{t('redesign.upload.draftBanner.subtitle')}</p>
          </div>
          <div className="ru-up-draft-banner__actions">
            <MotionPress
              type="button"
              variant="primary"
              onClick={handleContinueDraft}
            >
              {t('redesign.upload.draftBanner.continue')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              onClick={handleDiscardDraft}
            >
              {t('redesign.upload.draftBanner.discard')}
            </MotionPress>
          </div>
        </div>
      )}

      <div className="ru-up-panel">
        <AnimatePresence mode="wait">
          <m.div
            key={tab}
            initial={
              reduce ? false : { opacity: 0, y: 10 }
            }
            animate={{ opacity: 1, y: 0 }}
            exit={
              reduce ? undefined : { opacity: 0, y: -8 }
            }
            transition={transition}
          >
            {tab === 'file' && (
              <UploadFileTab
                key={
                  appliedDraft
                    ? `upload-file-${appliedDraft.savedAt}`
                    : 'upload-file-new'
                }
                onSuccess={handleSuccess}
                initialDraft={appliedDraft}
                onDiscardDraft={handleDiscardDraft}
              />
            )}
            {tab === 'soundcloud' && (
              <UploadSoundCloudTab
                onSuccess={handleSuccess}
              />
            )}
            {tab === 'bandcamp' && (
              <UploadBandcampTab
                onSuccess={handleSuccess}
              />
            )}
          </m.div>
        </AnimatePresence>
      </div>
    </section>
  )
}
