import { Icon } from '@/components/Icon/Icon'

interface Props {
  currentAvatar: string | null
  shownName: string
  username: string | undefined
  editMode: boolean
  displayName: string
  saving: boolean
  onEditStart: () => void
  onSave: () => void
  onCancel: () => void
  onDisplayNameChange: (name: string) => void
}

export function ProfileHero({
  currentAvatar,
  shownName,
  username,
  editMode,
  displayName,
  saving,
  onEditStart,
  onSave,
  onCancel,
  onDisplayNameChange,
}: Props) {
  return (
    <div className="profile-hero">
      <div className="profile-avatar">
        {currentAvatar
          ? <img src={currentAvatar} alt={shownName} />
          : shownName.charAt(0).toUpperCase()
        }
      </div>

      {editMode ? (
        <input
          className="form-input profile-name-input"
          value={displayName}
          onChange={(e) => onDisplayNameChange(e.target.value)}
          maxLength={64}
          placeholder="Отображаемое имя"
        />
      ) : (
        <div className="profile-name">{shownName}</div>
      )}

      {username && !editMode && (
        <div className="profile-username">@{username}</div>
      )}

      <div className="profile-edit-controls">
        {!editMode ? (
          <button className="profile-edit-btn" onClick={onEditStart}>
            <Icon name="edit" size={16} />
            <span>Изменить</span>
          </button>
        ) : (
          <>
            <button className="btn-primary" onClick={onSave} disabled={saving}>
              {saving ? 'Сохранение…' : 'Сохранить'}
            </button>
            <button className="profile-edit-cancel" onClick={onCancel}>
              Отмена
            </button>
          </>
        )}
      </div>
    </div>
  )
}
