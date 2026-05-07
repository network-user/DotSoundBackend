import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useBrandLabel } from '@/lib/brand'

interface Source {
  id: string
  label: string
  icon: string
  available: boolean
}

const SOURCES: Source[] = [
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
  return (
    <div className="import-sources ru-imp-root">
      <div className="view-header ru-imp-header">
        <h2>{t('redesign.upload.import.title')}</h2>
        <span className="hint ru-imp-subtitle">
          {t('redesign.upload.import.subtitle', { brand: brandLabel })}
        </span>
      </div>
      <div className="import-source-list ru-imp-list">
        {SOURCES.map((src) => (
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
                {t('redesign.upload.import.comingSoon')}
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
