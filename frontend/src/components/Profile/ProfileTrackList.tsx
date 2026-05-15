import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import {
  LongPressMenu,
  type LongPressMenuItem,
} from '@/components/ui/LongPressMenu'
import { useSound } from '@/store/SoundContext'
import { api } from '@/lib/api'
import {
  copyToClipboard,
  shareNatively,
} from '@/lib/platform'
import { showIsland } from '@/lib/island'
import type { Track } from '@/types/api'

interface Props {
  tracks: Track[]
  onPlay: (track: Track) => void
  onToggleVisibility: (track: Track) => void
  onDelete: (track: Track) => void
}

export function ProfileTrackList({
  tracks,
  onToggleVisibility,
  onDelete,
}: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const sound = useSound()
  const tap = () => sound.play('tapSoft')

  const handleDeleted = (trackId: number) => {
    const track = tracks.find((t) => t.id === trackId)
    if (track) onDelete(track)
  }

  const handleVisibilityChanged = (
    updated: Track,
  ) => {
    onToggleVisibility(updated)
  }

  const title = t(
    'profile.myTracksTitle',
    'Мои треки',
  )
  const isEmpty = tracks.length === 0

  return (
    <section
      className="profile-tracks-section"
      aria-label={title}
    >
      <h2 className="profile-tracks-section__title">
        {title}
        {!isEmpty && (
          <span className="profile-tracks-section__count">
            {tracks.length}
          </span>
        )}
      </h2>

      {isEmpty ? (
        <div className="profile-tracks-empty">
          <span className="profile-tracks-empty__icon">
            <Icon name="empty-staff" size={28} />
          </span>
          <div className="profile-tracks-empty__title">
            {t(
              'profile.myTracksEmptyTitle',
              'Здесь будут ваши треки',
            )}
          </div>
          <div className="profile-tracks-empty__hint">
            {t(
              'profile.myTracksEmptyHint',
              'Загрузите свой первый трек, чтобы он появился здесь',
            )}
          </div>
          <MotionPress
            type="button"
            variant="primary"
            haptic="medium"
            className="profile-tracks-empty__cta"
            onClick={() => {
              tap()
              navigate('/upload')
            }}
          >
            <Icon name="upload" size={16} />
            <span>
              {t(
                'profile.myTracksUpload',
                'Загрузить трек',
              )}
            </span>
          </MotionPress>
        </div>
      ) : (
        <div className="profile-tracks-section__list track-list">
          {tracks.map((track) => {
            const buildMenu = (): LongPressMenuItem[] => [
              {
                id: 'share',
                label: t('profile.trackAction.share', 'Поделиться'),
                icon: 'share',
                onPick: async () => {
                  try {
                    const links = await api.getShareLinks(track.id)
                    const url = links.url
                    const ok = await shareNatively({
                      url,
                      title: track.title,
                      text: track.artist || undefined,
                    })
                    if (!ok) {
                      const copied = await copyToClipboard(url)
                      showIsland({
                        kind: copied ? 'toast' : 'error',
                        title: copied
                          ? t('profile.trackAction.copied', 'Ссылка скопирована')
                          : t('profile.trackAction.copyFail', 'Не удалось скопировать'),
                        iconName: copied ? 'check' : 'alert-triangle',
                        durationMs: 2500,
                      })
                    }
                  } catch {
                    showIsland({
                      kind: 'error',
                      title: t(
                        'profile.trackAction.shareFail',
                        'Не удалось поделиться',
                      ),
                      iconName: 'alert-triangle',
                      durationMs: 2500,
                    })
                  }
                },
              },
              {
                id: 'open',
                label: t('profile.trackAction.open', 'Открыть страницу'),
                icon: 'external-link',
                onPick: () => {
                  navigate(`/track/${track.id}`)
                },
              },
              {
                id: 'visibility',
                label: track.is_public
                  ? t('profile.trackAction.makePrivate', 'Сделать приватным')
                  : t('profile.trackAction.makePublic', 'Сделать публичным'),
                icon: track.is_public ? 'lock' : 'globe',
                onPick: () => onToggleVisibility(track),
              },
              {
                id: 'delete',
                label: t('profile.trackAction.delete', 'Удалить'),
                icon: 'trash',
                destructive: true,
                onPick: () => onDelete(track),
              },
            ]
            return (
              <LongPressMenu key={track.id} items={buildMenu()}>
                <TrackCard
                  track={track}
                  contextTracks={tracks}
                  onDeleted={handleDeleted}
                  onVisibilityChanged={
                    handleVisibilityChanged
                  }
                />
              </LongPressMenu>
            )
          })}
        </div>
      )}
    </section>
  )
}
