import type { ChangeEvent, RefObject } from 'react'

interface Props {
  currentAvatar: string | null
  shownName: string
  username: string | undefined
  editMode: boolean
  displayName: string
  saving: boolean
  avatarInputRef: RefObject<HTMLInputElement>
  onEditStart: () => void
  onSave: () => void
  onCancel: () => void
  onDisplayNameChange: (name: string) => void
  onAvatarChange: (e: ChangeEvent<HTMLInputElement>) => void
}

export function ProfileHero({
  currentAvatar,
  shownName,
  username,
  editMode,
  displayName,
  saving,
  avatarInputRef,
  onEditStart,
  onSave,
  onCancel,
  onDisplayNameChange,
  onAvatarChange,
}: Props) {
  return (
    <div className="profile-hero">
      <div
        className={`profile-avatar${editMode ? ' editable' : ''}`}
        onClick={() => editMode && avatarInputRef.current?.click()}
      >
        {currentAvatar
          ? <img src={currentAvatar} alt={shownName} />
          : shownName.charAt(0).toUpperCase()
        }
        {editMode && <span className="avatar-edit-hint">✎</span>}
      </div>
      <input
        ref={avatarInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={onAvatarChange}
      />

      {editMode ? (
        <input
          className="form-input profile-name-input"
          value={displayName}
          onChange={(e) => onDisplayNameChange(e.target.value)}
          maxLength={128}
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
            ✎ Изменить
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
