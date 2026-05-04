import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'

interface ProfileActionsProps {
  onOpenImport: () => void
}

export function ProfileActions({ onOpenImport }: ProfileActionsProps) {
  const navigate = useNavigate()

  return (
    <div className="profile-actions">
      <button
        id="profile-action-upload"
        className="profile-action-btn"
        onClick={() => navigate('/upload')}
      >
        <span
          className="profile-action-icon profile-action-icon-svg"
        >
          <Icon name="upload" size={18} />
        </span>
        <span className="profile-action-label">Загрузить трек</span>
        <Icon
          name="chevron"
          size={16}
          className="profile-action-chevron"
        />
      </button>

      <button
        type="button"
        id="profile-action-import"
        className="profile-action-btn"
        onClick={onOpenImport}
      >
        <span
          className="profile-action-icon profile-action-icon-svg"
        >
          <Icon name="download" size={18} />
        </span>
        <span className="profile-action-label">
          Импортировать песни
        </span>
        <Icon
          name="chevron"
          size={16}
          className="profile-action-chevron"
        />
      </button>

      <button
        id="profile-action-playlists"
        className="profile-action-btn"
        onClick={() => navigate('/library?tab=playlists')}
      >
        <span
          className="profile-action-icon profile-action-icon-svg"
        >
          <Icon name="layers" size={18} />
        </span>
        <span className="profile-action-label">Мои плейлисты</span>
        <Icon
          name="chevron"
          size={16}
          className="profile-action-chevron"
        />
      </button>

      <button
        id="profile-action-liked"
        className="profile-action-btn"
        onClick={() => navigate('/library?tab=liked')}
      >
        <span
          className="profile-action-icon profile-action-icon-svg"
        >
          <Icon name="heart" size={18} />
        </span>
        <span className="profile-action-label">Понравившееся</span>
        <Icon
          name="chevron"
          size={16}
          className="profile-action-chevron"
        />
      </button>
    </div>
  )
}
