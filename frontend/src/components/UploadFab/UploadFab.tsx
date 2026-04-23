import { useLocation, useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { haptic } from '@/lib/telegram'

/** FAB только на лентах открытия, не на библиотеке/чатах (как SoundCloud / YT Music) */
const SHOW_ON_PATHS = new Set(['/', '/search'])

export function UploadFab() {
  const location = useLocation()
  const navigate = useNavigate()

  if (!SHOW_ON_PATHS.has(location.pathname)) return null

  return (
    <button
      type="button"
      className="upload-fab"
      aria-label="Загрузить трек"
      onClick={() => {
        haptic('medium')
        navigate('/upload')
      }}
    >
      <Icon name="plus" size={22} />
    </button>
  )
}
