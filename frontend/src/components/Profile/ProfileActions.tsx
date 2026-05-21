import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MIX_SHORTCUT_TILES } from '@/lib/homeShortcuts'
import { isYearRecapSeasonActive } from '@/lib/recapSeason'
import { useSound } from '@/store/SoundContext'

interface ProfileActionsProps {
  onOpenImport: () => void
  onOpenFavoriteArtists: () => void
  onOpenComplaints: () => void
  onOpenDislikes: () => void
  onOpenStats: () => void
}

interface ActionRow {
  id: string
  icon: string
  label: string
  onClick: () => void
}

interface ActionGroup {
  id: string
  title: string
  rows: ActionRow[]
}

export function ProfileActions({
  onOpenImport,
  onOpenFavoriteArtists,
  onOpenComplaints,
  onOpenDislikes,
  onOpenStats,
}: ProfileActionsProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const sound = useSound()
  const tap = () => sound.play('tapSoft')

  const catalogRows: ActionRow[] = [
    {
      id: 'profile-action-stats',
      icon: 'chart-bar',
      label: t('profile.tabStats', 'Статистика'),
      onClick: () => {
        tap()
        onOpenStats()
      },
    },
    {
      id: 'profile-action-upload',
      icon: 'upload',
      label: t(
        'redesign.library.actionUpload',
        'Загрузить трек',
      ),
      onClick: () => {
        tap()
        navigate('/upload')
      },
    },
    {
      id: 'profile-action-import',
      icon: 'download',
      label: t(
        'redesign.library.actionImport',
        'Импортировать песни',
      ),
      onClick: () => {
        tap()
        onOpenImport()
      },
    },
    {
      id: 'profile-action-playlists',
      icon: 'layers',
      label: t(
        'redesign.library.actionMyPlaylists',
        'Мои плейлисты',
      ),
      onClick: () => {
        tap()
        navigate('/library?tab=playlists')
      },
    },
    {
      id: 'profile-action-liked',
      icon: 'heart',
      label: t(
        'redesign.library.actionLiked',
        'Понравившееся',
      ),
      onClick: () => {
        tap()
        navigate('/library?tab=liked')
      },
    },
    {
      id: 'profile-action-artists',
      icon: 'users-following',
      label: t('profile.tabArtists'),
      onClick: () => {
        tap()
        onOpenFavoriteArtists()
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
    {
      id: 'profile-action-complaints',
      icon: 'flag',
      label: t('profile.tabComplaints'),
      onClick: () => {
        tap()
        onOpenComplaints()
      },
    },
  ]

  const discoverRows: ActionRow[] =
    MIX_SHORTCUT_TILES.map((tile) => ({
      id: `profile-mix-${tile.labelKey}`,
      icon: tile.profileIcon,
      label: t(`redesign.home.${tile.labelKey}`),
      onClick: () => {
        tap()
        navigate(tile.path)
      },
    }))

  if (isYearRecapSeasonActive()) {
    discoverRows.push({
      id: 'profile-action-recap',
      icon: 'sparkle',
      label: t('redesign.recap.profileEntry'),
      onClick: () => {
        tap()
        navigate('/recap')
      },
    })
  }

  const groups: ActionGroup[] = [
    {
      id: 'group-catalog',
      title: t(
        'profile.sectionCatalog',
        'Моя библиотека',
      ),
      rows: catalogRows,
    },
    {
      id: 'group-discover',
      title: t(
        'profile.sectionDiscover',
        'Подборки',
      ),
      rows: discoverRows,
    },
  ]

  return (
    <div className="profile-actions">
      {groups.map((group) =>
        group.rows.length === 0 ? null : (
          <section
            key={group.id}
            className="profile-actions-group"
            aria-label={group.title}
          >
            <h2 className="profile-actions-group__title">
              {group.title}
            </h2>
            <div
              className="rp-action-grid"
              role="list"
            >
              {group.rows.map((row) => (
                <MotionPress
                  key={row.id}
                  id={row.id}
                  type="button"
                  variant="ghost"
                  haptic="selection"
                  className="rp-action-tile"
                  role="listitem"
                  onClick={row.onClick}
                >
                  <span className="rp-action-tile__icon">
                    <Icon name={row.icon} size={18} />
                  </span>
                  <span className="rp-action-tile__label">
                    {row.label}
                  </span>
                </MotionPress>
              ))}
            </div>
          </section>
        ),
      )}
    </div>
  )
}
