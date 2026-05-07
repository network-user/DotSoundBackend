import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { hapticNotification } from '@/lib/telegram'
import { useSound } from '@/store/SoundContext'

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
  const { t } = useTranslation()
  const sound = useSound()
  const tap = () => sound.play('tapSoft')
  const handleSave = () => {
    hapticNotification('success')
    sound.play('notificationSuccess')
    onSave()
  }

  return (
    <div className="profile-hero">
      <div className="profile-avatar">
        {currentAvatar ? (
          <img src={currentAvatar} alt={shownName} />
        ) : (
          shownName.charAt(0).toUpperCase()
        )}
      </div>

      {editMode ? (
        <input
          className="form-input profile-name-input"
          value={displayName}
          onChange={(e) => onDisplayNameChange(e.target.value)}
          maxLength={64}
          placeholder={t(
            'redesign.library.profileNamePlaceholder',
            'Отображаемое имя',
          )}
        />
      ) : (
        <div className="profile-name">{shownName}</div>
      )}

      {username && !editMode && (
        <div className="profile-username">@{username}</div>
      )}

      <div className="profile-edit-controls">
        {!editMode ? (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="selection"
            className="profile-edit-btn"
            onClick={() => {
              tap()
              onEditStart()
            }}
          >
            <Icon name="edit" size={16} />
            <span>
              {t('redesign.library.profileNameEdit', 'Изменить')}
            </span>
          </MotionPress>
        ) : (
          <>
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              onClick={handleSave}
              disabled={saving}
            >
              {saving
                ? t('redesign.library.profileNameSaving', 'Сохранение…')
                : t('redesign.library.profileNameSave', 'Сохранить')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              className="profile-edit-cancel"
              onClick={() => {
                tap()
                onCancel()
              }}
            >
              {t('redesign.library.profileNameCancel', 'Отмена')}
            </MotionPress>
          </>
        )}
      </div>
    </div>
  )
}
