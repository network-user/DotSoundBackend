import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { usePlayerActions } from '@/store/PlayerContext'
import { useOptionalPrefetch } from '@/store/PrefetchContext'
import {
  getInternalUserId,
  haptic,
  hapticSelection,
  hapticTick,
  hapticNotification,
  isTelegram,
  setBackButton,
  tg,
} from '@/lib/telegram'
import { buildMiniAppAbsoluteUrl } from '@/lib/telegramBrowserHint'
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
import {
  getHlsQualityPreference,
  setHlsQualityPreference,
  type HlsQualityPreference,
} from '@/lib/hlsQualityPreference'
import { AccountDangerZone } from './AccountDangerZone'
import { ResetRecommendationsSection } from './ResetRecommendationsSection'
import { SettingsLegalSection } from './SettingsLegalSection'
import { LinkedAccounts } from './LinkedAccounts'
import { OAuthImportAccounts } from './OAuthImportAccounts'
import { TwoFASettings } from './TwoFASettings'
import { SettingsPickerModal } from './SettingsPickerModal'

interface Props {
  open: boolean
  onClose: () => void
  onLogout: () => void
}

const CACHE_LIMIT_OPTIONS = [
  { value: 'none', label: 'Без лимита', sublabel: 'Всё доступное место' },
  { value: '1gb', label: '1 ГБ', sublabel: '~200–300 треков' },
  { value: '5gb', label: '5 ГБ', sublabel: '~1000–1500 треков' },
  { value: '20gb', label: '20 ГБ', sublabel: '~4000–6000 треков' },
]

const TTL_OPTIONS = [
  { value: '1', label: '1 день', sublabel: 'Очень быстрая ротация' },
  { value: '3', label: '3 дня', sublabel: 'Рекомендуется' },
  { value: '7', label: '7 дней', sublabel: 'Неделя' },
  { value: '14', label: '14 дней', sublabel: 'Две недели' },
]

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
  const [cacheLimitModalOpen, setCacheLimitModalOpen] =
    useState(false)
  const [ttlModalOpen, setTtlModalOpen] = useState(false)
  const [hlsQualityModalOpen, setHlsQualityModalOpen] =
    useState(false)
  const [hlsQuality, setHlsQuality] =
    useState<HlsQualityPreference>(() => getHlsQualityPreference())
  const [profilePrivacyModalOpen, setProfilePrivacyModalOpen] =
    useState(false)
  const [accountExpanded, setAccountExpanded] =
    useState(false)
  const [profileVisibility, setProfileVisibility] = useState<
    'public' | 'followers_only' | 'hidden'
  >('public')

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
        if (u.profile_visibility) {
          setProfileVisibility(u.profile_visibility)
        }
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

  const profilePrivacyOptions = useMemo(
    () => [
      {
        value: 'public',
        label: t('settings.profilePrivacyPublic', {
          defaultValue: 'Открытый',
        }),
        sublabel: t('settings.profilePrivacyPublicSub', {
          defaultValue:
            'Профиль, треки, статистика и подписки видны всем, кто открывает страницу.',
        }),
      },
      {
        value: 'followers_only',
        label: t('settings.profilePrivacyFollowers', {
          defaultValue: 'Только подписчикам',
        }),
        sublabel: t('settings.profilePrivacyFollowersSub', {
          defaultValue:
            'Полный профиль, треки и статистика видны только тем, кто подписан на вас.',
        }),
      },
      {
        value: 'hidden',
        label: t('settings.profilePrivacyHidden', {
          defaultValue: 'Скрытый',
        }),
        sublabel: t('settings.profilePrivacyHiddenSub', {
          defaultValue:
            'Расширенный профиль и шаринг недоступны другим: минимальная публичная карточка без лишних данных.',
        }),
      },
    ],
    [t],
  )

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

  const handleProfileVisibility = async (
    next: 'public' | 'followers_only' | 'hidden',
  ) => {
    if (profileVisibility === next) return
    feedbackTap()
    try {
      const u = await api.updateProfile(
        undefined,
        undefined,
        next,
      )
      setProfileVisibility(
        u.profile_visibility ?? 'public',
      )
      hapticNotification('success')
    } catch {
      hapticNotification('error')
      showIsland({
        kind: 'error',
        title: t(
          'settings.profilePrivacySaveFail',
          'Не удалось сохранить настройки',
        ),
        iconName: 'alert-triangle',
        durationMs: 4000,
      })
    }
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
    value: string,
  ) => {
    setCacheLimit(value as CacheLimitChoice)
    setCacheLimitChoice(value as CacheLimitChoice)
    hapticSelection()
  }

  const handleHlsQualityChange = (value: string) => {
    const next: HlsQualityPreference =
      value === 'lo' || value === 'hi' ? value : 'auto'
    setHlsQuality(next)
    setHlsQualityPreference(next)
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
    value: string,
  ) => {
    const days = Number.parseInt(value, 10)
    setTtlDays(days)
    setUnpinnedTtlDays(days)
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
    if (isTelegram()) {
      try {
        const wa = tg as {
          openLink?: (u: string) => void
        }
        wa.openLink?.(buildMiniAppAbsoluteUrl())
      } catch {
        /* ignore */
      }
      return
    }
    window.open(window.location.href, '_blank')
  }

  const handleInstallHint = () => {
    feedbackTap()
    showIsland({
      kind: 'toast',
      title: t('settings.pwaInstallHint'),
      hint: t('settings.pwaInstallHintHint'),
      durationMs: 8800,
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

  const currentLang = i18n.language?.startsWith('ru')
    ? 'ru'
    : 'en'

  const cacheLimitLabel =
    CACHE_LIMIT_OPTIONS.find(
      (o) => o.value === cacheLimit,
    )?.label ?? '—'

  const ttlLabel =
    TTL_OPTIONS.find(
      (o) => o.value === String(ttlDays),
    )?.label ?? `${ttlDays} дн.`

  const hlsQualityOptions = useMemo(
    () => [
      {
        value: 'auto',
        label: t('settings.qualityAuto', {
          defaultValue: 'Авто',
        }),
        sublabel: t('settings.qualityAutoSub', {
          defaultValue:
            'Подбирается под скорость соединения и режим экономии трафика.',
        }),
      },
      {
        value: 'lo',
        label: t('settings.qualityLow', {
          defaultValue: 'Эконом',
        }),
        sublabel: t('settings.qualityLowSub', {
          defaultValue:
            'Меньше трафика и быстрый старт. Подходит для слабой сети.',
        }),
      },
      {
        value: 'hi',
        label: t('settings.qualityHigh', {
          defaultValue: 'Высокое',
        }),
        sublabel: t('settings.qualityHighSub', {
          defaultValue:
            'Максимальное доступное качество. Расход трафика выше.',
        }),
      },
    ],
    [t],
  )

  const hlsQualityLabel =
    hlsQualityOptions.find((o) => o.value === hlsQuality)?.label ??
    hlsQualityOptions[0]?.label ??
    'Авто'

  const profilePrivacyLabel =
    profilePrivacyOptions.find(
      (o) => o.value === profileVisibility,
    )?.label ?? '—'

  return (
    <>
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

            {/* ── Звук ─────────────────────────────────── */}
            <div className="settings-section-header">
              {t('settings.sectionSound', {
                defaultValue: 'Звук',
              })}
            </div>

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

            <div className="settings-item settings-item--volume">
              <div className="settings-volume-label">
                <Icon name="slider" size={20} />
                <span>
                  {t('settings.interfaceSoundLevel', {
                    defaultValue: 'Громкость UI',
                  })}
                </span>
                <span className="settings-volume-pct">
                  {Math.round(soundVolume * 100)}%
                </span>
              </div>
              <input
                className="settings-range settings-range--full"
                type="range"
                min={0}
                max={100}
                step={5}
                value={Math.round(soundVolume * 100)}
                onChange={(e) =>
                  handleSoundVolumeChange(
                    Number(e.target.value) / 100,
                  )
                }
              />
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

            {/* ── Оффлайн ──────────────────────────────── */}
            <div className="settings-section-header">
              {t('settings.sectionOffline', {
                defaultValue: 'Оффлайн',
              })}
            </div>

            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="settings-item settings-item--nav"
              onClick={() => {
                feedbackTap()
                setHlsQualityModalOpen(true)
              }}
            >
              <Icon name="headphones" size={20} />
              <span>
                {t('settings.streamQuality', {
                  defaultValue: 'Качество звука',
                })}
              </span>
              <span className="settings-item-value">
                {hlsQualityLabel}
              </span>
              <Icon
                name="chevron"
                size={16}
                className="settings-chevron"
              />
            </MotionPress>

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
                        'Авто-сохранение лайков',
                    })}
                  </span>
                  <div
                    className={`settings-toggle${autoCacheEnabled ? ' on' : ''}`}
                  >
                    <div className="settings-toggle-dot" />
                  </div>
                </div>

                {autoCacheEnabled && (
                  <>
                    <MotionPress
                      type="button"
                      variant="ghost"
                      haptic="light"
                      className="settings-item settings-item--nav"
                      onClick={() => {
                        feedbackTap()
                        setCacheLimitModalOpen(true)
                      }}
                    >
                      <Icon name="layers" size={20} />
                      <span>
                        {t('settings.offlineLimit', {
                          defaultValue:
                            'Лимит оффлайн-кеша',
                        })}
                      </span>
                      <span className="settings-item-value">
                        {cacheLimitLabel}
                      </span>
                      <Icon
                        name="chevron"
                        size={16}
                        className="settings-chevron"
                      />
                    </MotionPress>

                    <MotionPress
                      type="button"
                      variant="ghost"
                      haptic="light"
                      className="settings-item settings-item--nav"
                      onClick={() => {
                        feedbackTap()
                        setTtlModalOpen(true)
                      }}
                    >
                      <Icon name="clock" size={20} />
                      <span>
                        {t('settings.offlineUnpinnedTtl', {
                          days: ttlDays,
                          defaultValue:
                            'Хранить прогрев',
                        })}
                      </span>
                      <span className="settings-item-value">
                        {ttlLabel}
                      </span>
                      <Icon
                        name="chevron"
                        size={16}
                        className="settings-chevron"
                      />
                    </MotionPress>

                    <div className="settings-item settings-item--feedback">
                      <Icon name="info" size={20} />
                      <span>
                        {t('settings.offlineUsage', {
                          used: formatBytes(storage.used),
                          quota: formatBytes(
                            storage.quota,
                          ),
                          defaultValue:
                            'Использовано {{used}} из {{quota}}',
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

                    {breakdown &&
                      breakdown.count > 0 &&
                      breakdown.byPinned.unpinned > 0 && (
                        <div className="settings-item settings-item--feedback">
                          <Icon name="info" size={20} />
                          <span>
                            {t(
                              'settings.offlineBreakdown',
                              {
                                pinned: formatBytes(
                                  breakdown.byPinned
                                    .pinned,
                                ),
                                unpinned: formatBytes(
                                  breakdown.byPinned
                                    .unpinned,
                                ),
                                defaultValue:
                                  'Сохранено: {{pinned}} · Прогрев: {{unpinned}}',
                              },
                            )}
                          </span>
                          <MotionPress
                            type="button"
                            variant="ghost"
                            haptic="medium"
                            className="settings-mini-btn"
                            onClick={handleClearAutoCache}
                          >
                            {t(
                              'settings.offlineClearAuto',
                              {
                                defaultValue:
                                  'Очистить прогрев',
                              },
                            )}
                          </MotionPress>
                        </div>
                      )}
                  </>
                )}
              </>
            )}

            {/* ── Интерфейс ────────────────────────────── */}
            <div className="settings-section-header">
              {t('settings.sectionInterface', {
                defaultValue: 'Интерфейс',
              })}
            </div>

            <div className="settings-item settings-item--lang">
              <Icon name="globe" size={20} />
              <span>{t('settings.language')}</span>
              <div className="settings-lang-pills">
                <button
                  type="button"
                  className={`settings-lang-pill${currentLang === 'ru' ? ' settings-lang-pill--active' : ''}`}
                  onClick={() =>
                    handleLanguageChange('ru')
                  }
                >
                  RU
                </button>
                <button
                  type="button"
                  className={`settings-lang-pill${currentLang === 'en' ? ' settings-lang-pill--active' : ''}`}
                  onClick={() =>
                    handleLanguageChange('en')
                  }
                >
                  EN
                </button>
              </div>
            </div>

            <div className="settings-section-gap" />

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

            <div className="settings-section-gap--xl" />

            {/* ── Аккаунт ──────────────────────────────── */}
            <div className="settings-section-header">
              {t('settings.sectionAccount', {
                defaultValue: 'Аккаунт',
              })}
            </div>

            <LinkedAccounts />

            <OAuthImportAccounts />

            <TwoFASettings
              enabled={twoFAEnabled}
              onToggle={setTwoFAEnabled}
            />

            <div className="settings-section-gap--md" />

            <div className="settings-section-header">
              {t('settings.profilePrivacy', {
                defaultValue: 'Профиль для других',
              })}
            </div>

            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="settings-item settings-item--nav"
              onClick={() => {
                feedbackTap()
                setProfilePrivacyModalOpen(true)
              }}
            >
              <Icon name="eye" size={20} />
              <span>
                {t('settings.profilePrivacyChoice', {
                  defaultValue: 'Видимость профиля',
                })}
              </span>
              <span className="settings-item-value">
                {profilePrivacyLabel}
              </span>
              <Icon
                name="chevron"
                size={16}
                className="settings-chevron"
              />
            </MotionPress>

            <div className="settings-section-gap" />

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

            <div className="settings-section-gap--sm" />

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
              <span>
                {t('settings.trashLink', 'Корзина треков')}
              </span>
              <Icon
                name="chevron"
                size={16}
                className="settings-chevron"
              />
            </MotionPress>

            <div className="settings-section-gap--lg" />

            <ResetRecommendationsSection onClose={onClose} />
            <SettingsLegalSection />

            <div className="settings-section-gap--lg" />

            <div className="settings-account-expand">
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="settings-account-expand__trigger"
                onClick={() => {
                  haptic('light')
                  setAccountExpanded((v) => !v)
                }}
              >
                <Icon name="trash" size={18} />
                <span>
                  {t(
                    'settings.dangerSection',
                    'Управление аккаунтом',
                  )}
                </span>
                <Icon
                  name="chevron"
                  size={16}
                  className={`settings-chevron settings-expand-chevron${accountExpanded ? ' rotated' : ''}`}
                />
              </MotionPress>
              {accountExpanded && (
                <div className="settings-account-expand__body">
                  <AccountDangerZone />
                </div>
              )}
            </div>
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

      <SettingsPickerModal
        open={cacheLimitModalOpen}
        onClose={() => setCacheLimitModalOpen(false)}
        title={t('settings.offlineLimit', {
          defaultValue: 'Лимит оффлайн-кеша',
        })}
        description={t(
          'settings.offlineLimitDesc',
          {
            defaultValue:
              'Максимальный объём хранилища для автоматически кешированных треков. При достижении лимита старые непрослушанные треки будут удаляться.',
          },
        )}
        options={CACHE_LIMIT_OPTIONS}
        value={cacheLimit}
        onChange={handleCacheLimitChange}
      />

      <SettingsPickerModal
        open={ttlModalOpen}
        onClose={() => setTtlModalOpen(false)}
        title={t('settings.offlineUnpinnedTtlTitle', {
          defaultValue: 'Хранить прогрев',
        })}
        description={t(
          'settings.offlineTtlDesc',
          {
            defaultValue:
              'Прогрев — треки, предзагруженные автоматически, но не добавленные в избранное. Эта настройка определяет, сколько дней они хранятся на устройстве перед удалением.',
          },
        )}
        options={TTL_OPTIONS}
        value={String(ttlDays)}
        onChange={handleTtlChange}
      />

      <SettingsPickerModal
        open={profilePrivacyModalOpen}
        onClose={() => setProfilePrivacyModalOpen(false)}
        title={t('settings.profilePrivacy', {
          defaultValue: 'Профиль для других',
        })}
        description={t('settings.profilePrivacyPickerDesc', {
          defaultValue:
            'Кто видит ваш профиль, публичные треки и статистику. Изменить можно в любой момент.',
        })}
        options={profilePrivacyOptions}
        value={profileVisibility}
        onChange={(value) =>
          void handleProfileVisibility(
            value as 'public' | 'followers_only' | 'hidden',
          )
        }
        optionLayout="stacked"
      />

      <SettingsPickerModal
        open={hlsQualityModalOpen}
        onClose={() => setHlsQualityModalOpen(false)}
        title={t('settings.streamQuality', {
          defaultValue: 'Качество звука',
        })}
        description={t('settings.streamQualityDesc', {
          defaultValue:
            'Управляет HLS-вариантом, который выбирается при включении и предзагрузке треков. «Авто» подстраивается под скорость соединения и режим экономии трафика.',
        })}
        options={hlsQualityOptions}
        value={hlsQuality}
        onChange={handleHlsQualityChange}
        optionLayout="stacked"
      />
    </>
  )
}
