import {
  type ChangeEvent,
  useRef,
} from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useSound } from '@/store/SoundContext'

const _ALLOWED_AVATAR_MIMES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
])
const _MAX_AVATAR_BYTES = 2 * 1024 * 1024

function _avatarFileIssue(
  file: File,
): 'type' | 'size' | null {
  if (file.size > _MAX_AVATAR_BYTES) return 'size'
  const mime = file.type
  if (mime && _ALLOWED_AVATAR_MIMES.has(mime)) {
    return null
  }
  if (
    mime === '' ||
    mime === 'application/octet-stream'
  ) {
    return /\.jpe?g$/i.test(file.name) ||
      /\.png$/i.test(file.name) ||
      /\.webp$/i.test(file.name)
      ? null
      : 'type'
  }
  return 'type'
}

interface Props {
  avatarImageUrl: string | null
  shownName: string
  username: string | undefined
  editMode: boolean
  displayName: string
  saving: boolean
  onEditStart: () => void
  onSave: () => void
  onCancel: () => void
  onDisplayNameChange: (name: string) => void
  onAvatarFileSelected: (file: File) => void
  onAvatarRejected: (
    reason: 'type' | 'size',
  ) => void
}

export function ProfileHero({
  avatarImageUrl,
  shownName,
  username,
  editMode,
  displayName,
  saving,
  onEditStart,
  onSave,
  onCancel,
  onDisplayNameChange,
  onAvatarFileSelected,
  onAvatarRejected,
}: Props) {
  const { t } = useTranslation()
  const sound = useSound()
  const avatarInputRef = useRef<HTMLInputElement>(null)
  const tap = () => sound.play('tapSoft')
  const handleSave = () => {
    tap()
    onSave()
  }

  const onAvatarInputChange = (
    ev: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = ev.target.files?.[0]
    ev.target.value = ''
    if (!file || saving) return
    const issue = _avatarFileIssue(file)
    if (issue) {
      onAvatarRejected(issue)
      return
    }
    onAvatarFileSelected(file)
  }

  const avatarVisual = (
    <>
      {avatarImageUrl ? (
        <img src={avatarImageUrl} alt="" />
      ) : (
        shownName.charAt(0).toUpperCase()
      )}
      {editMode && (
        <>
          <input
            ref={avatarInputRef}
            type="file"
            hidden
            accept="image/jpeg,image/png,image/webp"
            onChange={onAvatarInputChange}
          />
          {!saving && (
            <span className="profile-avatar-edit-hint">
              <Icon name="image" size={22} />
            </span>
          )}
        </>
      )}
    </>
  )

  return (
    <div className="profile-hero">
      {editMode ? (
        <MotionPress
          type="button"
          variant="ghost"
          disabled={saving}
          ariaLabel={t(
            'redesign.library.profileAvatarChangeAria',
          )}
          className="profile-avatar profile-avatar--editable"
          onClick={() => {
            if (saving) return
            tap()
            avatarInputRef.current?.click()
          }}
        >
          {avatarVisual}
        </MotionPress>
      ) : (
        <div className="profile-avatar">{avatarVisual}</div>
      )}

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
