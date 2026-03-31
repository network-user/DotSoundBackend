interface Props {
  onNavigate: (view: 'liked' | 'playlists' | 'upload') => void
}

export function ProfileActions({ onNavigate }: Props) {
  return (
    <div className="profile-actions">
      <button
        id="profile-action-upload"
        className="profile-action-btn"
        onClick={() => onNavigate('upload')}
      >
        <span className="profile-action-icon">↑</span>
        <span className="profile-action-label">Загрузить трек</span>
        <span className="profile-action-chevron">›</span>
      </button>

      <button
        id="profile-action-playlists"
        className="profile-action-btn"
        onClick={() => onNavigate('playlists')}
      >
        <span className="profile-action-icon">▤</span>
        <span className="profile-action-label">Мои плейлисты</span>
        <span className="profile-action-chevron">›</span>
      </button>

      <button
        id="profile-action-liked"
        className="profile-action-btn"
        onClick={() => onNavigate('liked')}
      >
        <span className="profile-action-icon">♥</span>
        <span className="profile-action-label">Понравившееся</span>
        <span className="profile-action-chevron">›</span>
      </button>
    </div>
  )
}
