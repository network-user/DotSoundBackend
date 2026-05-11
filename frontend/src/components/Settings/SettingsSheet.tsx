import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import { useOptionalPrefetch } from '@/store/PrefetchContext'
import {
  getInternalUserId,
  haptic,
  hapticSelection,
  hapticNotification,
  hapticTick,
  setBackButton,
} from '@/lib/telegram'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useExitTransition } from '@/hooks/useExitTransition'
import { canInstallPwa } from '@/components/PwaInstall/InstallPrompt'
import { showIsland } from '@/lib/island'
import { useSound } from '@/store/SoundContext'
import {
  clearAllOffline,
  clearUnpinned,
  getAutoCacheEnabled,
  getCacheLimitChoice,
  getStorageBreakdown,
  getStorageInfo,
  getUnpinnedTtlDays,
  isOfflineCacheSupported,
  runCacheGC,
  setAutoCacheEnabled,
  setCacheLimitChoice,
  setUnpinnedTtlDays,
  type CacheLimitChoice,
  type StorageBreakdown,
} from '@/lib/offlineCache'
import { AccountDangerZone } from './AccountDangerZone'
import { ResetRecommendationsSection } from './ResetRecommendationsSection'
import { SettingsLegalSection } from './SettingsLegalSection'
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
  const navigate = useNavigate()
  const { openEq } = usePlayerActions()
  const sound = useSound()
  const prefetchCtx = useOptionalPrefetch()
  const [smartBufferingEnabled, setSmartBufferingEnabled] =
    useState<boolean>(
      () =>
        localStorage.getItem('setting-smart-buffering') !==
        'false',
    )
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
  const [autoCacheEnabled, setAutoCacheEnabledState] =
    useState<boolean>(() => getAutoCacheEnabled())
  const [cacheLimit, setCacheLimit] =
    useState<CacheLimitChoice>(() => getCacheLimitChoice())
  const [storage, setStorage] = useState<{
    used: number
    quota: number
  }>({ used: 0, quota: 0 })
  const [breakdown, setBreakdown] = useState<StorageBreakdown | null>(
    null,
  )
  const [ttlDays, setTtlDays] = useState<number>(() =>
    getUnpinnedTtlDays(),
  )

  useEffect(() => {
    if (!open) return
    if (!isOfflineCacheSupported()) return
    void getStorageInfo().then(setStorage)
    void getStorageBreakdown().then(setBreakdown)
  }, [open])

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

  const handleSmartBufferingToggle = () => {
    feedbackTap()
    const next = !smartBufferingEnabled
    setSmartBufferingEnabled(next)
    localStorage.setItem(
      'setting-smart-buffering',
      String(next),
    )
    prefetchCtx?.setEnabled(next)
  }

  const handleAutoCacheToggle = () => {
    feedbackTap()
    const next = !autoCacheEnabled
    setAutoCacheEnabledState(next)
    setAutoCacheEnabled(next)
  }

  const handleCacheLimitChange = (
    value: CacheLimitChoice,
  ) => {
    setCacheLimit(value)
    setCacheLimitChoice(value)
    hapticSelection()
  }

  const handleClearOffline = async () => {
    feedbackTap()
    await clearAllOffline()
    setStorage(await getStorageInfo())
    setBreakdown(await getStorageBreakdown())
    showIsland({
      kind: 'toast',
      title: t('settings.offlineClearDone', {
        defaultValue: 'Оффлайн-кеш очищен',
      }),
      durationMs: 2200,
    })
  }

  const handleClearAutoCache = async () => {
    feedbackTap()
    const removed = await clearUnpinned()
    setStorage(await getStorageInfo())
    setBreakdown(await getStorageBreakdown())
    showIsland({
      kind: 'toast',
      title: t('settings.offlineAutoClearDone', {
        count: removed,
        defaultValue:
          'Удалено {{count}} временных треков',
      }),
      durationMs: 2400,
    })
  }

  const handleTtlChange = (
    value: number,
  ) => {
    setTtlDays(value)
    setUnpinnedTtlDays(value)
    hapticSelection()
    void runCacheGC({ force: true }).then(async () => {
      setStorage(await getStorageInfo())
      setBreakdown(await getStorageBreakdown())
    })
  }

  const formatBytes = (n: number): string => {
    if (!n || n <= 0) return '0 МБ'
    const mb = n / (1024 * 1024)
    if (mb < 1024) return `${mb.toFixed(0)} МБ`
    return `${(mb / 1024).toFixed(2)} ГБ`
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
    showIsland({
      kind: 'toast',
      title: t('settings.pwaInstallHint'),
      durationMs: 7000,
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
    showIsland({
      kind: 'toast',
      title: t('settings.testSoundFired', {
        defaultValue: 'Тест звука отправлен',
      }),
      durationMs: 1200,
    })
  }

  const handleTestHaptic = () => {
    haptic('light')
    hapticNotification('success')
    showIsland({
      kind: 'toast',
      title: t('settings.testHapticFired', {
        defaultValue: 'Тест вибрации отправлен',
      }),
      durationMs: 1200,
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
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="settings-back"
            ariaLabel={t('common.back')}
            onClick={onClose}
          >
            <Icon
              name="chevron"
              size={20}
              className="back-chevron"
            />
            <span className="settings-back-label">
              {t('common.back')}
            </span>
          </MotionPress>
          <span className="settings-title">
            {t('settings.title')}
          </span>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn settings-close"
            ariaLabel={t('common.close')}
            onClick={onClose}
          >
            <Icon name="x" size={18} />
          </MotionPress>
        </div>

        <div className="settings-list">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
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
          </MotionPress>

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
            onClick={handleSmartBufferingToggle}
          >
            <Icon name="download" size={20} />
            <span>
              {t('settings.smartBuffering', {
                defaultValue: 'Умная буферизация',
              })}
            </span>
            <div
              className={`settings-toggle${smartBufferingEnabled ? ' on' : ''}`}
            >
              <div className="settings-toggle-dot" />
            </div>
          </div>

          {isOfflineCacheSupported() && (
            <>
              <div
                className="settings-item"
                onClick={handleAutoCacheToggle}
              >
                <Icon name="cloud-download" size={20} />
                <span>
                  {t('settings.offlineAutoCache', {
                    defaultValue:
                      'Авто-сохранение лайкнутых треков',
                  })}
                </span>
                <div
                  className={`settings-toggle${autoCacheEnabled ? ' on' : ''}`}
                >
                  <div className="settings-toggle-dot" />
                </div>
              </div>

              {autoCacheEnabled && (
                <div className="settings-item">
                  <Icon name="layers" size={20} />
                  <span>
                    {t('settings.offlineLimit', {
                      defaultValue: 'Лимит оффлайн-кеша',
                    })}
                  </span>
                  <select
                    className="settings-select"
                    value={cacheLimit}
                    onChange={(e) =>
                      handleCacheLimitChange(
                        e.target
                          .value as CacheLimitChoice,
                      )
                    }
                  >
                    <option value="none">
                      {t('settings.offlineLimitNone', {
                        defaultValue: 'Без лимита',
                      })}
                    </option>
                    <option value="1gb">1 ГБ</option>
                    <option value="5gb">5 ГБ</option>
                    <option value="20gb">20 ГБ</option>
                  </select>
                </div>
              )}

              {autoCacheEnabled && (
                <div className="settings-item settings-item--feedback">
                  <Icon name="info" size={20} />
                  <span>
                    {t('settings.offlineUsage', {
                      used: formatBytes(storage.used),
                      quota: formatBytes(storage.quota),
                      defaultValue:
                        'Используется {{used}} из {{quota}}',
                    })}
                  </span>
                  <MotionPress
                    type="button"
                    variant="ghost"
                    haptic="medium"
                    className="settings-mini-btn"
                    onClick={handleClearOffline}
                  >
                    {t('settings.offlineClear', {
                      defaultValue: 'Очистить',
                    })}
                  </MotionPress>
                </div>
              )}

              {autoCacheEnabled && breakdown && breakdown.count > 0 && (
                <div className="settings-item settings-item--feedback">
                  <Icon name="info" size={20} />
                  <span>
                    {t('settings.offlineBreakdown', {
                      pinned: formatBytes(
                        breakdown.byPinned.pinned,
                      ),
                      unpinned: formatBytes(
                        breakdown.byPinned.unpinned,
                      ),
                      defaultValue:
                        'Сохранено: {{pinned}} · Прогрев: {{unpinned}}',
                    })}
                  </span>
                  {breakdown.byPinned.unpinned > 0 && (
                    <MotionPress
                      type="button"
                      variant="ghost"
                      haptic="medium"
                      className="settings-mini-btn"
                      onClick={handleClearAutoCache}
                    >
                      {t('settings.offlineClearAuto', {
                        defaultValue: 'Очистить прогрев',
                      })}
                    </MotionPress>
                  )}
                </div>
              )}

              {autoCacheEnabled && (
                <div className="settings-item">
                  <Icon name="clock" size={20} />
                  <span>
                    {t('settings.offlineUnpinnedTtl', {
                      days: ttlDays,
                      defaultValue:
                        'Хранить прогрев: {{days}} дн.',
                    })}
                  </span>
                  <select
                    className="settings-select"
                    value={String(ttlDays)}
                    onChange={(e) =>
                      handleTtlChange(
                        Number.parseInt(
                          e.currentTarget.value,
                          10,
                        ),
                      )
                    }
                  >
                    <option value="1">1</option>
                    <option value="3">3</option>
                    <option value="7">7</option>
                    <option value="14">14</option>
                  </select>
                </div>
              )}
            </>
          )}

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
              <MotionPress
                type="button"
                variant="ghost"
                haptic="selection"
                className="settings-mini-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  handleTestSound()
                }}
              >
                {t('settings.testSound', {
                  defaultValue: 'Звук',
                })}
              </MotionPress>
              <MotionPress
                type="button"
                variant="ghost"
                haptic="selection"
                className="settings-mini-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  handleTestHaptic()
                }}
              >
                {t('settings.testHaptic', {
                  defaultValue: 'Вибро',
                })}
              </MotionPress>
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

          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
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
          </MotionPress>

          {installable && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
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
            </MotionPress>
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
            type="button"
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

          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="settings-item"
          >
            <Icon name="info" size={20} />
            <span>
              {t('settings.aboutApp')}
            </span>
            <span className="settings-version">
              v0.1.0
            </span>
          </MotionPress>

          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="settings-item"
            onClick={() => {
              onClose()
              navigate('/trash')
            }}
          >
            <Icon name="trash" size={20} />
            <span>{t('settings.trashLink', 'Корзина треков')}</span>
          </MotionPress>

          <ResetRecommendationsSection onClose={onClose} />
          <SettingsLegalSection />
          <AccountDangerZone />
        </div>

        <div className="settings-footer">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="medium"
            className="settings-logout"
            onClick={onLogout}
          >
            <Icon name="log-out" size={18} />
            {t('settings.logOut')}
          </MotionPress>
        </div>
      </div>
    </div>
  )
}
