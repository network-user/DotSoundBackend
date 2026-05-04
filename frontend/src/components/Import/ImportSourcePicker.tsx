import { Icon } from '@/components/Icon/Icon'
import { useBrandLabel } from '@/lib/brand'

interface Source {
  id: string
  label: string
  icon: string
  available: boolean
}

const SOURCES: Source[] = [
  {
    id: 'telegram',
    label: 'Telegram',
    icon: 'source-telegram',
    available: true,
  },
  {
    id: 'yandex',
    label: 'Яндекс Музыка',
    icon: 'source-yandex',
    available: true,
  },
  {
    id: 'vk',
    label: 'VK Музыка',
    icon: 'source-vk',
    available: false,
  },
  {
    id: 'spotify',
    label: 'Spotify',
    icon: 'source-spotify',
    available: true,
  },
  {
    id: 'soundcloud',
    label: 'SoundCloud',
    icon: 'source-soundcloud',
    available: true,
  },
]

interface Props {
  onSelect: (sourceId: string) => void
}

export function ImportSourcePicker({
  onSelect,
}: Props) {
  const brandLabel = useBrandLabel()
  return (
    <div className="import-sources">
      <div className="view-header">
        <h2>Импорт музыки</h2>
        <span className="hint">
          Перенеси свою музыку в {brandLabel}
        </span>
      </div>
      <div className="import-source-list">
        {SOURCES.map((src) => (
          <button
            key={src.id}
            className={`import-source-btn${
              !src.available ? ' disabled' : ''
            }`}
            disabled={!src.available}
            onClick={() =>
              src.available && onSelect(src.id)
            }
          >
            <span className="import-source-icon">
              <Icon name={src.icon} size={22} />
            </span>
            <span className="import-source-label">
              {src.label}
            </span>
            {!src.available && (
              <span className="import-source-badge">
                скоро
              </span>
            )}
            {src.available && (
              <span className="profile-action-chevron">
                ›
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
