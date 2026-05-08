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

  const triggerAvatarPick = () => {
    if (saving) return
    tap()
    avatarInputRef.current?.click()
  }

  const avatarInner = avatarImageUrl ? (
    <img src={avatarImageUrl} alt="" />
  ) : (
    <span aria-hidden>
      {shownName.charAt(0).toUpperCase()}
    </span>
  )

  return (
    <div className="profile-hero">
      <div className="profile-hero__avatar-wrap">
        {editMode ? (
          <MotionPress
            type="button"
            variant="ghost"
            disabled={saving}
            ariaLabel={t(
              'redesign.library.profileAvatarChangeAria',
            )}
            className="profile-avatar profile-avatar--editable"
            onClick={triggerAvatarPick}
          >
            {avatarInner}
            {!saving && (
              <span className="profile-avatar-edit-hint">
                <Icon name="image" size={20} />
              </span>
            )}
          </MotionPress>
        ) : (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="selection"
            ariaLabel={t(
              'profile.avatarEditHint',
              'Сменить фото профиля',
            )}
            className="profile-avatar profile-avatar--clickable"
            onClick={() => {
              tap()
              onEditStart()
            }}
          >
            {avatarInner}
            <span
              aria-hidden
              className="profile-avatar-hover-hint"
            >
              <Icon name="edit" size={18} />
            </span>
          </MotionPress>
        )}
        <input
          ref={avatarInputRef}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp"
          onChange={onAvatarInputChange}
        />
      </div>

      {editMode ? (
        <input
          className="form-input profile-name-input"
          value={displayName}
          onChange={(e) =>
            onDisplayNameChange(e.target.value)
          }
          maxLength={64}
          placeholder={t(
            'redesign.library.profileNamePlaceholder',
            'Отображаемое имя',
          )}
        />
      ) : (
        <div className="profile-name">
          {shownName}
        </div>
      )}

      {username && !editMode && (
        <div className="profile-username">
          @{username}
        </div>
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
              {t(
                'profile.editProfile',
                'Изменить профиль',
              )}
            </span>
          </MotionPress>
        ) : (
          <>
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary profile-edit-save"
              onClick={() => {
                tap()
                onSave()
              }}
              disabled={saving}
            >
              {saving
                ? t(
                    'redesign.library.profileNameSaving',
                    'Сохранение…',
                  )
                : t(
                    'redesign.library.profileNameSave',
                    'Сохранить',
                  )}
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
              disabled={saving}
            >
              {t(
                'redesign.library.profileNameCancel',
                'Отмена',
              )}
            </MotionPress>
          </>
        )}
      </div>
    </div>
  )
}
