import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MIX_SHORTCUT_TILES } from '@/lib/homeShortcuts'
import { isYearRecapSeasonActive } from '@/lib/recapSeason'
import { useSound } from '@/store/SoundContext'

interface ProfileActionsProps {
  onOpenImport: () => void
  onOpenDislikes: () => void
}

interface ActionRow {
  id: string
  icon: string
  label: string
  onClick: () => void
}

export function ProfileActions({
  onOpenImport,
  onOpenDislikes,
}: ProfileActionsProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const sound = useSound()
  const tap = () => sound.play('tapSoft')

  const recapRow: ActionRow | null =
    isYearRecapSeasonActive()
      ? {
          id: 'profile-action-recap',
          icon: 'sparkle',
          label: t('redesign.recap.profileEntry'),
          onClick: () => {
            tap()
            navigate('/recap')
          },
        }
      : null

  const mixRows: ActionRow[] =
    MIX_SHORTCUT_TILES.map((tile) => ({
      id: `profile-mix-${tile.labelKey}`,
      icon: tile.profileIcon,
      label: t(`redesign.home.${tile.labelKey}`),
      onClick: () => {
        tap()
        navigate(tile.path)
      },
    }))

  const rows: ActionRow[] = [
    {
      id: 'profile-action-upload',
      icon: 'upload',
      label: t('redesign.library.actionUpload', 'Загрузить трек'),
      onClick: () => {
        tap()
        navigate('/upload')
      },
    },
    {
      id: 'profile-action-import',
      icon: 'download',
      label: t('redesign.library.actionImport', 'Импортировать песни'),
      onClick: () => {
        tap()
        onOpenImport()
      },
    },
    {
      id: 'profile-action-playlists',
      icon: 'layers',
      label: t('redesign.library.actionMyPlaylists', 'Мои плейлисты'),
      onClick: () => {
        tap()
        navigate('/library?tab=playlists')
      },
    },
    {
      id: 'profile-action-liked',
      icon: 'heart',
      label: t('redesign.library.actionLiked', 'Понравившееся'),
      onClick: () => {
        tap()
        navigate('/library?tab=liked')
      },
    },
    {
      id: 'profile-action-dislikes',
      icon: 'thumbs-down',
      label: t('profile.tabDislikes'),
      onClick: () => {
        tap()
        onOpenDislikes()
      },
    },
    ...mixRows,
    ...(recapRow ? [recapRow] : []),
  ]

  return (
    <div className="profile-actions">
      {rows.map((row) => (
        <MotionPress
          key={row.id}
          id={row.id}
          type="button"
          variant="ghost"
          haptic="selection"
          className="profile-action-btn"
          onClick={row.onClick}
        >
          <span className="profile-action-icon profile-action-icon-svg">
            <Icon name={row.icon} size={18} />
          </span>
          <span className="profile-action-label">{row.label}</span>
          <Icon
            name="chevron"
            size={16}
            className="profile-action-chevron"
          />
        </MotionPress>
      ))}
    </div>
  )
}
