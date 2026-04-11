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
    icon: '✈️',
    available: true,
  },
  {
    id: 'vk',
    label: 'VK Музыка',
    icon: '🎵',
    available: false,
  },
  {
    id: 'yandex',
    label: 'Яндекс Музыка',
    icon: '🎧',
    available: false,
  },
  {
    id: 'spotify',
    label: 'Spotify',
    icon: '🟢',
    available: false,
  },
  {
    id: 'soundcloud',
    label: 'SoundCloud',
    icon: '☁️',
    available: false,
  },
]

interface Props {
  onSelect: (sourceId: string) => void
}

export function ImportSourcePicker({
  onSelect,
}: Props) {
  return (
    <div className="import-sources">
      <div className="view-header">
        <h2>Импорт музыки</h2>
        <span className="hint">
          Перенеси свою музыку в .sound
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
              {src.icon}
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
