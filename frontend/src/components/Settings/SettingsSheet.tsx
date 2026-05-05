import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import {
  getInternalUserId,
  haptic,
  hapticSelection,
  hapticNotification,
  hapticTick,
  setBackButton,
} from '@/lib/telegram'
import { Icon } from '@/components/Icon/Icon'
import { useExitTransition } from '@/hooks/useExitTransition'
import { canInstallPwa } from '@/components/PwaInstall/InstallPrompt'
import { useToast } from '@/components/ui/Toast'
import { useSound } from '@/store/SoundContext'
import { AccountDangerZone } from './AccountDangerZone'
import { LinkedAccounts } from './LinkedAccounts'
import { OAuthImportAccounts } from './OAuthImportAccounts'
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
  const sound = useSound()
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
  const [soundEnabled, setSoundEnabled] =
    useState<boolean>(() => sound.enabled)
  const [soundVolume, setSoundVolume] =
    useState<number>(() => sound.volume)

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
  const toast = useToast()
  const installable = canInstallPwa()
  const feedbackTap = () => {
    hapticSelection()
    sound.play('tapSoft')
  }

  const handleEq = () => {
    feedbackTap()
    onClose()
    openEq()
  }

  const handleVideoToggle = () => {
    feedbackTap()
    const next = !videoEnabled
    setVideoEnabled(next)
    localStorage.setItem(
      'setting-video-enabled',
      String(next),
    )
  }

  const handleMonoToggle = () => {
    feedbackTap()
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
    feedbackTap()
    i18n.changeLanguage(lng)
    const uid = getInternalUserId()
    if (uid) {
      api.updateProfile(undefined, lng).catch(() => {})
    }
  }

  const handleOpenBrowser = () => {
    feedbackTap()
    window.open(
      window.location.href,
      '_blank',
    )
  }

  const handleInstallHint = () => {
    feedbackTap()
    toast.info(t('settings.pwaInstallHint'), {
      duration: 7000,
    })
  }

  const handleSoundToggle = () => {
    feedbackTap()
    const next = !soundEnabled
    setSoundEnabled(next)
    sound.setEnabled(next)
    if (next) {
      sound.play('tapSoft')
    }
  }

  const handleSoundVolumeChange = (value: number) => {
    const clamped = Math.max(
      0,
      Math.min(1, value),
    )
    setSoundVolume(clamped)
    sound.setVolume(clamped)
    hapticTick()
  }

  const handleTestSound = () => {
    feedbackTap()
    sound.playTest('tapSoft')
    toast.info(
      t('settings.testSoundFired', {
        defaultValue: 'Тест звука отправлен',
      }),
      { duration: 1200 },
    )
  }

  const handleTestHaptic = () => {
    haptic('light')
    hapticNotification('success')
    toast.info(
      t('settings.testHapticFired', {
        defaultValue: 'Тест вибрации отправлен',
      }),
      { duration: 1200 },
    )
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

          <div
            className="settings-item"
            onClick={handleSoundToggle}
          >
            <Icon
              name="volume-high"
              size={20}
            />
            <span>
              {t('settings.interfaceSounds', {
                defaultValue: 'Звуки интерфейса',
              })}
            </span>
            <div
              className={`settings-toggle${soundEnabled ? ' on' : ''}`}
            >
              <div className="settings-toggle-dot" />
            </div>
          </div>

          <div className="settings-item">
            <Icon name="slider" size={20} />
            <span>
              {t('settings.interfaceSoundLevel', {
                defaultValue: 'Громкость UI',
              })}
            </span>
            <input
              className="settings-range"
              type="range"
              min={0}
              max={100}
              step={10}
              value={Math.round(soundVolume * 100)}
              onChange={(e) =>
                handleSoundVolumeChange(
                  Number(e.target.value) / 100,
                )
              }
            />
          </div>

          <div className="settings-item settings-item--feedback">
            <Icon name="sparkle" size={20} />
            <span>
              {t('settings.interfaceFeedbackTest', {
                defaultValue: 'Проверка отклика',
              })}
            </span>
            <div className="settings-inline-actions">
              <button
                type="button"
                className="settings-mini-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  handleTestSound()
                }}
              >
                {t('settings.testSound', {
                  defaultValue: 'Звук',
                })}
              </button>
              <button
                type="button"
                className="settings-mini-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  handleTestHaptic()
                }}
              >
                {t('settings.testHaptic', {
                  defaultValue: 'Вибро',
                })}
              </button>
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

          <OAuthImportAccounts />

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

          <AccountDangerZone />
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
