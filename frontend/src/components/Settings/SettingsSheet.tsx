import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import {
  getInternalUserId,
  setBackButton,
} from '@/lib/telegram'
import { Icon } from '@/components/Icon/Icon'
import { useExitTransition } from '@/hooks/useExitTransition'
import { canInstallPwa } from '@/components/PwaInstall/InstallPrompt'
import { useToast } from '@/components/ui/Toast'
import { LinkedAccounts } from './LinkedAccounts'
import { TwoFASettings } from './TwoFASettings'

interface Props {
  open: boolean
  onClose: () => void
  onLogout: () => void
}

export function SettingsSheet({
  open,
  onClose,
  onLogout,
}: Props) {
  const { t, i18n } = useTranslation()
  const { openEq } = usePlayerActions()
  const [videoEnabled, setVideoEnabled] =
    useState(
      () =>
        localStorage.getItem(
          'setting-video-enabled',
        ) !== 'false',
    )
  const [monoEnabled, setMonoEnabled] =
    useState(
      () =>
        localStorage.getItem(
          'setting-monochrome',
        ) === 'true',
    )
  const [twoFAEnabled, setTwoFAEnabled] =
    useState(false)

  useEffect(() => {
    if (!open) return
    const userId = getInternalUserId()
    if (!userId) return
    api
      .getUserProfile(userId)
      .then((u) => {
        setTwoFAEnabled(
          u.totp_enabled ?? false,
        )
      })
      .catch(() => {})
  }, [open])

  useEffect(() => {
    if (!open) return
    const cleanup = setBackButton(true, onClose)
    return cleanup
  }, [open, onClose])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  const exit = useExitTransition(open)
  if (!exit.mounted) return null

  const handleEq = () => {
    onClose()
    openEq()
  }

  const handleVideoToggle = () => {
    const next = !videoEnabled
    setVideoEnabled(next)
    localStorage.setItem(
      'setting-video-enabled',
      String(next),
    )
  }

  const handleMonoToggle = () => {
    const next = !monoEnabled
    setMonoEnabled(next)
    localStorage.setItem(
      'setting-monochrome',
      String(next),
    )
    document.body.classList.toggle(
      'monochrome',
      next,
    )
  }

  const handleLanguageChange = (lng: string) => {
    i18n.changeLanguage(lng)
    const uid = getInternalUserId()
    if (uid) {
      api.updateProfile(undefined, lng).catch(() => {})
    }
  }

  const handleOpenBrowser = () => {
    window.open(
      window.location.href,
      '_blank',
    )
  }

  const toast = useToast()
  const installable = canInstallPwa()
  const handleInstallHint = () => {
    toast.info(t('settings.pwaInstallHint'), {
      duration: 7000,
    })
  }

  return (
    <div
      className={`settings-backdrop${exit.cls}`}
      onClick={(e) => {
        if (e.target === e.currentTarget)
          onClose()
      }}
    >
      <div className={`settings-sheet${exit.cls}`}>
        <div className="settings-handle" />
        <div className="settings-header">
          <button
            className="settings-back"
            onClick={onClose}
            aria-label={t('common.back')}
          >
            <Icon
              name="chevron"
              size={20}
              className="back-chevron"
            />
            <span className="settings-back-label">
              {t('common.back')}
            </span>
          </button>
          <span className="settings-title">
            {t('settings.title')}
          </span>
          <button
            className="icon-btn settings-close"
            onClick={onClose}
            aria-label={t('common.close')}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="settings-list">
          <button
            className="settings-item"
            onClick={handleEq}
          >
            <Icon name="eq" size={20} />
            <span>{t('settings.eq')}</span>
            <Icon
              name="chevron"
              size={16}
              className="settings-chevron"
            />
          </button>

          <div
            className="settings-item"
            onClick={handleVideoToggle}
          >
            <Icon name="video" size={20} />
            <span>{t('settings.video')}</span>
            <div
              className={`settings-toggle${videoEnabled ? ' on' : ''}`}
            >
              <div className="settings-toggle-dot" />
            </div>
          </div>

          <div
            className="settings-item"
            onClick={handleMonoToggle}
          >
            <Icon name="moon" size={20} />
            <span>{t('settings.monochrome')}</span>
            <div
              className={`settings-toggle${monoEnabled ? ' on' : ''}`}
            >
              <div className="settings-toggle-dot" />
            </div>
          </div>

          <div className="settings-item">
            <Icon name="globe" size={20} />
            <span>{t('settings.language')}</span>
            <select
              className="settings-select"
              value={i18n.language?.startsWith('ru') ? 'ru' : 'en'}
              onChange={(e) => handleLanguageChange(e.target.value)}
            >
              <option value="ru">{t('settings.languageRu')}</option>
              <option value="en">{t('settings.languageEn')}</option>
            </select>
          </div>

          <button
            className="settings-item"
            onClick={handleOpenBrowser}
          >
            <Icon name="maximize" size={20} />
            <span>
              {t('settings.openInBrowser')}
            </span>
            <Icon
              name="chevron"
              size={16}
              className="settings-chevron"
            />
          </button>

          {installable && (
            <button
              className="settings-item"
              onClick={handleInstallHint}
            >
              <Icon name="install" size={20} />
              <span>
                {t('settings.installAsApp')}
              </span>
              <Icon
                name="chevron"
                size={16}
                className="settings-chevron"
              />
            </button>
          )}

          <div className="settings-hint">
            {t('settings.lockScreenHint')}
          </div>

          <LinkedAccounts />

          <TwoFASettings
            enabled={twoFAEnabled}
            onToggle={setTwoFAEnabled}
          />

          <button
            className="settings-item disabled"
            disabled
          >
            <Icon
              name="volume-high"
              size={20}
            />
            <span>{t('settings.soundQuality')}</span>
            <span className="settings-badge">
              {t('settings.comingSoon')}
            </span>
          </button>

          <button className="settings-item">
            <Icon name="info" size={20} />
            <span>
              {t('settings.aboutApp')}
            </span>
            <span className="settings-version">
              v0.1.0
            </span>
          </button>
        </div>

        <div className="settings-footer">
          <button
            className="settings-logout"
            onClick={onLogout}
          >
            <Icon name="log-out" size={18} />
            {t('settings.logOut')}
          </button>
        </div>
      </div>
    </div>
  )
}
