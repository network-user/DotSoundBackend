import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useBrandLabel } from '@/lib/brand'
import { isTelegram } from '@/lib/telegram'
import { api } from '@/lib/api'

interface Source {
  id: string
  label: string
  icon: string
  available: boolean
  /** Reason shown next to the row when not available. */
  unavailableReasonKey?: string
  unavailableReasonFallback?: string
}

const BASE_SOURCES: Source[] = [
  { id: 'telegram', label: 'Telegram', icon: 'source-telegram', available: true },
  { id: 'yandex', label: 'Яндекс Музыка', icon: 'source-yandex', available: true },
  { id: 'vk', label: 'VK Музыка', icon: 'source-vk', available: false },
  { id: 'spotify', label: 'Spotify', icon: 'source-spotify', available: false },
  { id: 'soundcloud', label: 'SoundCloud', icon: 'source-soundcloud', available: true },
]

interface Props {
  onSelect: (sourceId: string) => void
}

export function ImportSourcePicker({ onSelect }: Props) {
  const { t } = useTranslation()
  const brandLabel = useBrandLabel()
  const [telegramLinked, setTelegramLinked] = useState<boolean>(
    () => isTelegram(),
  )

  useEffect(() => {
    if (isTelegram()) {
      setTelegramLinked(true)
      return
    }
    api
      .getLinkStatus()
      .then((s) => {
        setTelegramLinked(Boolean(s.telegram_linked))
      })
      .catch(() => {
        setTelegramLinked(false)
      })
  }, [])

  const sources: Source[] = BASE_SOURCES.map((src) => {
    if (src.id !== 'telegram') return src
    if (telegramLinked) return src
    return {
      ...src,
      available: false,
      unavailableReasonKey: 'redesign.upload.import.requiresTelegramLink',
      unavailableReasonFallback:
        'Привяжите Telegram в настройках',
    }
  })
  return (
    <div className="import-sources ru-imp-root">
      <div className="view-header ru-imp-header">
        <h2>{t('redesign.upload.import.title')}</h2>
        <span className="hint ru-imp-subtitle">
          {t('redesign.upload.import.subtitle', { brand: brandLabel })}
        </span>
      </div>
      <div className="import-source-list ru-imp-list">
        {sources.map((src) => (
          <MotionPress
            key={src.id}
            type="button"
            variant="ghost"
            haptic={src.available ? 'selection' : null}
            disabled={!src.available}
            ariaLabel={t('redesign.upload.import.openSourceAria', {
              name: src.label,
            })}
            className={
              src.available
                ? 'ru-imp-row'
                : 'ru-imp-row ru-imp-row--disabled'
            }
            onClick={() => {
              if (src.available) onSelect(src.id)
            }}
          >
            <span className="ru-imp-row__icon" aria-hidden>
              <Icon name={src.icon} size={22} />
            </span>
            <span className="ru-imp-row__label">{src.label}</span>
            {!src.available && (
              <span className="ru-imp-row__badge">
                {src.unavailableReasonKey
                  ? t(src.unavailableReasonKey, {
                      defaultValue:
                        src.unavailableReasonFallback ??
                        t('redesign.upload.import.comingSoon'),
                    })
                  : t('redesign.upload.import.comingSoon')}
              </span>
            )}
            {src.available && (
              <span className="ru-imp-row__chevron" aria-hidden>
                <Icon name="chevron" size={16} />
              </span>
            )}
          </MotionPress>
        ))}
      </div>
    </div>
  )
}
