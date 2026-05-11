import type { CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MIX_SHORTCUT_TILES } from '@/lib/homeShortcuts'
import { isYearRecapSeasonActive } from '@/lib/recapSeason'
import { useSound } from '@/store/SoundContext'

interface ProfileActionsProps {
  onOpenImport: () => void
  onOpenComplaints: () => void
  onOpenDislikes: () => void
  onOpenStats: () => void
}

interface ActionRow {
  id: string
  icon: string
  label: string
  tone: string
  onClick: () => void
}

interface ActionGroup {
  id: string
  title: string
  rows: ActionRow[]
}

const TONE_BG: Record<string, string> = {
  blue: 'linear-gradient(135deg, #4f8af0 0%, #2c5dbf 100%)',
  purple: 'linear-gradient(135deg, #9c6bf7 0%, #6940c9 100%)',
  pink: 'linear-gradient(135deg, #ee5e91 0%, #c83a76 100%)',
  red: 'linear-gradient(135deg, #f06464 0%, #b73a3a 100%)',
  orange: 'linear-gradient(135deg, #ff9959 0%, #d3672b 100%)',
  amber: 'linear-gradient(135deg, #f1c34d 0%, #c98c1f 100%)',
  green: 'linear-gradient(135deg, #4cc987 0%, #2a9b65 100%)',
  teal: 'linear-gradient(135deg, #4ec4c7 0%, #2c8b8e 100%)',
  slate: 'linear-gradient(135deg, #6b7585 0%, #3f4756 100%)',
  pinkish: 'linear-gradient(135deg, #f78fa8 0%, #c45a78 100%)',
}

export function ProfileActions({
  onOpenImport,
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
      tone: 'blue',
      label: t('profile.tabStats', 'Статистика'),
      onClick: () => {
        tap()
        onOpenStats()
      },
    },
    {
      id: 'profile-action-upload',
      icon: 'upload',
      tone: 'green',
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
      tone: 'teal',
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
      tone: 'purple',
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
      tone: 'pink',
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
      id: 'profile-action-dislikes',
      icon: 'thumbs-down',
      tone: 'slate',
      label: t('profile.tabDislikes'),
      onClick: () => {
        tap()
        onOpenDislikes()
      },
    },
    {
      id: 'profile-action-complaints',
      icon: 'flag',
      tone: 'red',
      label: t('profile.tabComplaints'),
      onClick: () => {
        tap()
        onOpenComplaints()
      },
    },
  ]

  const discoverTones = ['orange', 'amber', 'pinkish', 'teal']
  const discoverRows: ActionRow[] =
    MIX_SHORTCUT_TILES.map((tile, idx) => ({
      id: `profile-mix-${tile.labelKey}`,
      icon: tile.profileIcon,
      tone: discoverTones[idx % discoverTones.length],
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
      tone: 'amber',
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
                  <span
                    className="rp-action-tile__icon"
                    style={
                      {
                        '--rp-tile-bg':
                          TONE_BG[row.tone] || TONE_BG.slate,
                      } as CSSProperties
                    }
                  >
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
