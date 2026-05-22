import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { ProfileShareModal } from '@/components/Profile/ProfileShareModal'
import { TrackList } from '@/components/TrackList/TrackList'
import { MotionPress } from '@/components/ui/MotionPress'
import { api, getApiErrorMessage } from '@/lib/api'
import { showIsland } from '@/lib/island'
import { playFromPaginatedCollection } from '@/lib/paginatedPlayback'
import {
  getInternalUserId,
  haptic,
  hapticNotification,
} from '@/lib/telegram'
import { usePlayerActions } from '@/store/PlayerContext'
import type {
  Track,
  UserResponse,
  UserStatsResponse,
} from '@/types/api'

import '@/styles/redesign-profile.css'

const PROFILE_PAGE_SIZE = 20
const LIKED_QUEUE_SIZE = 80

type PublicProfileTab = 'tracks' | 'liked' | 'stats'

export function PublicProfileView() {
  const { t } = useTranslation()
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const previewOwnProfile = useMemo(() => {
    const params = new URLSearchParams(location.search)
    return params.get('preview') === '1'
  }, [location.search])
  const { playTrack } = usePlayerActions()
  const currentUserId = getInternalUserId()
  const viewedUserId = Number(userId)
  const validUserId =
    Number.isInteger(viewedUserId) && viewedUserId > 0

  const [profile, setProfile] = useState<UserResponse | null>(null)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [stats, setStats] = useState<UserStatsResponse | null>(null)
  const [tracks, setTracks] = useState<Track[]>([])
  const [tracksTotal, setTracksTotal] = useState(0)
  const [tracksPage, setTracksPage] = useState(1)
  const [likedTracks, setLikedTracks] = useState<Track[]>([])
  const [likedTotal, setLikedTotal] = useState(0)
  const [likedPage, setLikedPage] = useState(1)
  const [following, setFollowing] = useState<boolean | null>(null)
  const [tab, setTab] = useState<PublicProfileTab>('tracks')
  const [loading, setLoading] = useState(true)
  const [contentLoading, setContentLoading] = useState(false)
  const [tracksMoreLoading, setTracksMoreLoading] = useState(false)
  const [likedMoreLoading, setLikedMoreLoading] = useState(false)
  const [followLoading, setFollowLoading] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isOwnProfile =
    currentUserId !== null && currentUserId === viewedUserId
  const accessFull = profile?.profile_access === 'full'

  const resetContent = useCallback(() => {
    setStats(null)
    setTracks([])
    setTracksTotal(0)
    setTracksPage(1)
    setLikedTracks([])
    setLikedTotal(0)
    setLikedPage(1)
    setTab('tracks')
  }, [])

  const loadTracksPage = useCallback(
    async (page: number, reset: boolean) => {
      if (!validUserId) return
      if (reset) {
        setTracks([])
        setTracksTotal(0)
      } else {
        setTracksMoreLoading(true)
      }
      try {
        const res = await api.getAuthorTracks(
          viewedUserId,
          page,
          PROFILE_PAGE_SIZE,
        )
        setTracks((prev) =>
          reset ? res.items : [...prev, ...res.items],
        )
        setTracksTotal(res.total)
        setTracksPage(page)
      } catch {
        if (reset) {
          setTracks([])
          setTracksTotal(0)
        }
      } finally {
        if (!reset) setTracksMoreLoading(false)
      }
    },
    [validUserId, viewedUserId],
  )

  const loadLikedPage = useCallback(
    async (page: number, reset: boolean) => {
      if (!validUserId) return
      if (reset) {
        setLikedTracks([])
        setLikedTotal(0)
      } else {
        setLikedMoreLoading(true)
      }
      try {
        const res = await api.getLikedTracks(
          viewedUserId,
          page,
          PROFILE_PAGE_SIZE,
          undefined,
          'newest',
        )
        setLikedTracks((prev) =>
          reset ? res.items : [...prev, ...res.items],
        )
        setLikedTotal(res.total)
        setLikedPage(page)
      } catch {
        if (reset) {
          setLikedTracks([])
          setLikedTotal(0)
        }
      } finally {
        if (!reset) setLikedMoreLoading(false)
      }
    },
    [validUserId, viewedUserId],
  )

  const loadProfile = useCallback(async () => {
    if (!validUserId) {
      navigate('/profile', { replace: true })
      return
    }
    if (isOwnProfile && !previewOwnProfile) {
      navigate('/profile', { replace: true })
      return
    }

    setLoading(true)
    setError(null)
    setProfile(null)
    setAvatarUrl(null)
    setFollowing(null)
    resetContent()

    try {
      const user = await api.getUserProfile(viewedUserId)
      setProfile(user)
      void api
        .getAvatarUrl(viewedUserId)
        .then((res) => setAvatarUrl(res.avatar_url))
        .catch(() => setAvatarUrl(null))
      if (currentUserId) {
        void api
          .getFollowStatus(viewedUserId)
          .then((res) => setFollowing(Boolean(res.following)))
          .catch(() => setFollowing(null))
      }
      if (user.profile_access === 'full') {
        setContentLoading(true)
        await Promise.all([
          api
            .getUserStats(viewedUserId)
            .then(setStats)
            .catch(() => setStats(null)),
          loadTracksPage(1, true),
          loadLikedPage(1, true),
        ])
        setContentLoading(false)
      }
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          t('profile.public.loadFailed', 'Не удалось открыть профиль'),
        ),
      )
    } finally {
      setLoading(false)
      setContentLoading(false)
    }
  }, [
    currentUserId,
    isOwnProfile,
    loadLikedPage,
    loadTracksPage,
    navigate,
    resetContent,
    t,
    previewOwnProfile,
    validUserId,
    viewedUserId,
  ])

  useEffect(() => {
    void loadProfile()
  }, [loadProfile])

  const displayName = useMemo(() => {
    if (!profile) return ''
    return (
      profile.display_name ||
      [profile.first_name, profile.last_name]
        .filter(Boolean)
        .join(' ') ||
      profile.username ||
      t('profile.public.defaultName', 'Профиль')
    )
  }, [profile, t])

  const closeProfile = () => {
    haptic('light')
    if (location.key !== 'default') {
      navigate(-1)
      return
    }
    navigate('/')
  }

  const handleFollow = async () => {
    if (!profile || followLoading) return
    const previousFollowing = following
    const previousStats = stats
    const nextFollowing = !(following === true)
    setFollowing(nextFollowing)
    if (stats) {
      setStats({
        ...stats,
        followers_count: Math.max(
          0,
          stats.followers_count + (nextFollowing ? 1 : -1),
        ),
      })
    }
    setFollowLoading(true)
    haptic('medium')
    try {
      const res = await api.toggleFollow(profile.id)
      setFollowing(Boolean(res.following))
      await loadProfile()
    } catch (err) {
      setFollowing(previousFollowing)
      setStats(previousStats)
      hapticNotification('error')
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(
          err,
          t(
            'profile.public.followFailed',
            'Не удалось обновить подписку',
          ),
        ),
        iconName: 'alert-triangle',
        durationMs: 3600,
      })
    } finally {
      setFollowLoading(false)
    }
  }

  const playLikedTrack = useCallback(
    async (track: Track) => {
      await playFromPaginatedCollection({
        track,
        loadedTracks: likedTracks,
        playTrack,
        loadQueue: async (current, fallbackTracks) => {
          const excludeIds = fallbackTracks.map((item) => item.id)
          const queue = await api.getLikedPlaybackQueue(
            viewedUserId,
            current.id,
            LIKED_QUEUE_SIZE,
            undefined,
            'newest',
            false,
            excludeIds,
          )
          return [current, ...queue.next_tracks]
        },
      })
    },
    [likedTracks, playTrack, viewedUserId],
  )

  const tabs: Array<{
    id: PublicProfileTab
    icon: string
    label: string
    count: number | null
  }> = [
    {
      id: 'tracks',
      icon: 'music',
      label: t('profile.public.tabTracks', 'Треки'),
      count: tracksTotal,
    },
    {
      id: 'liked',
      icon: 'heart',
      label: t('profile.public.tabLiked', 'Любимое'),
      count: likedTotal,
    },
    {
      id: 'stats',
      icon: 'chart-bar',
      label: t('profile.public.tabStats', 'Статистика'),
      count: null,
    },
  ]

  const trackHasMore = tracks.length < tracksTotal
  const likedHasMore = likedTracks.length < likedTotal

  return (
    <section
      id="view-public-profile"
      data-testid="public-profile-view"
      className="view active rp-public-profile"
    >
      <header className="profile-page-header profile-page-header--sub">
        <MotionPress
          type="button"
          variant="ghost"
          haptic="selection"
          className="profile-subview-back"
          ariaLabel={t('profile.public.close', 'Закрыть профиль')}
          onClick={closeProfile}
        >
          <Icon name="chevron-left" size={18} />
          <span>{t('common.back', 'Назад')}</span>
        </MotionPress>
        <h1 className="profile-page-title profile-page-title--sub">
          {t('profile.public.title', 'Профиль')}
        </h1>
        <div className="profile-header-actions profile-header-actions--sub">
          {accessFull && profile ? (
            <MotionPress
              type="button"
              variant="icon"
              haptic="light"
              className="icon-btn"
              ariaLabel={t('profile.share.open')}
              data-testid="public-profile-share-open"
              onClick={() => setShareOpen(true)}
            >
              <Icon name="share" size={20} />
            </MotionPress>
          ) : (
            <span aria-hidden className="profile-page-spacer" />
          )}
        </div>
      </header>

      <div className="profile-content rp-public-profile__content">
        {loading ? (
          <div className="rp-public-profile__loading">
            <div className="loader" />
          </div>
        ) : error ? (
          <div className="rp-public-profile__empty">
            <Icon name="alert-triangle" size={28} />
            <p>{error}</p>
          </div>
        ) : profile ? (
          <>
            <section className="rp-public-hero">
              <div className="rp-public-hero__avatar">
                {avatarUrl ? (
                  <img
                    src={avatarUrl}
                    alt=""
                    onError={(event) => {
                      event.currentTarget.style.display = 'none'
                    }}
                  />
                ) : (
                  <Icon name="user" size={30} />
                )}
              </div>
              <div className="rp-public-hero__body">
                <h2 className="rp-public-hero__name">
                  {displayName}
                </h2>
                {profile.username && (
                  <p className="rp-public-hero__username">
                    @{profile.username}
                  </p>
                )}
              </div>

              <div className="rp-public-hero__actions">
                {currentUserId && (
                  <MotionPress
                    type="button"
                    variant={following ? 'ghost' : 'primary'}
                    haptic="medium"
                    className="rp-public-follow"
                    data-active={following ? 'true' : 'false'}
                    disabled={followLoading}
                    onClick={() => void handleFollow()}
                  >
                    <Icon
                      name={following ? 'check' : 'user-plus'}
                      size={16}
                    />
                    <span>
                      {followLoading
                        ? t('common.loading', 'Загрузка...')
                        : following
                          ? t(
                              'artist.following',
                              'Подписан',
                            )
                          : t(
                              'artist.follow',
                              'Подписаться',
                            )}
                    </span>
                  </MotionPress>
                )}
                {accessFull && (
                  <MotionPress
                    type="button"
                    variant="ghost"
                    haptic="light"
                    className="rp-public-share"
                    onClick={() => setShareOpen(true)}
                  >
                    <Icon name="share-arrow" size={16} />
                    <span>
                      {t(
                        'profile.share.shareNative',
                        'Поделиться',
                      )}
                    </span>
                  </MotionPress>
                )}
              </div>
            </section>

            {profile.profile_access === 'limited' ? (
              <div className="rp-public-profile__empty">
                <Icon
                  name={
                    profile.profile_visibility === 'followers_only'
                      ? 'users-following'
                      : 'lock'
                  }
                  size={28}
                />
                <p>
                  {profile.profile_visibility === 'followers_only'
                    ? t(
                        'profile.public.followersOnly',
                        'Треки, любимое и статистика видны подписчикам.',
                      )
                    : t(
                        'profile.public.hidden',
                        'Пользователь скрыл расширенный профиль.',
                      )}
                </p>
              </div>
            ) : (
              <>
                <ProfileSummary stats={stats} />

                <nav
                  className="rp-public-tabs"
                  aria-label={t(
                    'profile.public.tabsAria',
                    'Разделы профиля',
                  )}
                >
                  {tabs.map((item) => (
                    <MotionPress
                      key={item.id}
                      type="button"
                      variant={tab === item.id ? 'primary' : 'ghost'}
                      haptic="selection"
                      className="rp-public-tabs__button"
                      aria-pressed={tab === item.id}
                      onClick={() => setTab(item.id)}
                    >
                      <Icon name={item.icon} size={16} />
                      <span>{item.label}</span>
                      {item.count !== null && item.count > 0 && (
                        <span className="rp-public-tabs__count">
                          {item.count}
                        </span>
                      )}
                    </MotionPress>
                  ))}
                </nav>

                {contentLoading ? (
                  <div className="rp-public-profile__loading">
                    <div className="loader" />
                  </div>
                ) : (
                  <div className="rp-public-panel">
                    {tab === 'tracks' && (
                      <>
                        <TrackList
                          tracks={tracks}
                          contextTracks={tracks}
                          emptyMessage={t(
                            'profile.public.noTracks',
                            'Публичных треков пока нет',
                          )}
                        />
                        {trackHasMore && (
                          <LoadMoreButton
                            loading={tracksMoreLoading}
                            onClick={() =>
                              void loadTracksPage(
                                tracksPage + 1,
                                false,
                              )
                            }
                          />
                        )}
                      </>
                    )}
                    {tab === 'liked' && (
                      <>
                        <TrackList
                          tracks={likedTracks}
                          flavor="liked"
                          contextTracks={likedTracks}
                          emptyMessage={t(
                            'profile.public.noLiked',
                            'Любимых треков пока нет',
                          )}
                          onPlayTrack={(track) => {
                            void playLikedTrack(track)
                          }}
                        />
                        {likedHasMore && (
                          <LoadMoreButton
                            loading={likedMoreLoading}
                            onClick={() =>
                              void loadLikedPage(
                                likedPage + 1,
                                false,
                              )
                            }
                          />
                        )}
                      </>
                    )}
                    {tab === 'stats' && (
                      <PublicStatsPanel stats={stats} />
                    )}
                  </div>
                )}
              </>
            )}
          </>
        ) : null}
      </div>

      {profile && (
        <ProfileShareModal
          open={shareOpen}
          userId={profile.id}
          onClose={() => setShareOpen(false)}
        />
      )}
    </section>
  )
}

function ProfileSummary({
  stats,
}: {
  stats: UserStatsResponse | null
}) {
  const { t } = useTranslation()
  return (
    <div className="profile-stats rp-public-summary">
      <div className="stat-item">
        <div className="stat-value">{stats?.total_tracks ?? 0}</div>
        <div className="stat-label">
          {t('author.statsTracks', 'Треков')}
        </div>
      </div>
      <div className="stat-item">
        <div className="stat-value">
          {formatCompact(stats?.total_plays ?? 0)}
        </div>
        <div className="stat-label">
          {t('author.statsPlays', 'Прослушиваний')}
        </div>
      </div>
      <div className="stat-item">
        <div className="stat-value">
          {formatCompact(stats?.followers_count ?? 0)}
        </div>
        <div className="stat-label">
          {t('author.statsFollowers', 'Подписчиков')}
        </div>
      </div>
      <div className="stat-item">
        <div className="stat-value">
          {formatCompact(stats?.total_likes ?? 0)}
        </div>
        <div className="stat-label">
          {t('author.statsLikes', 'Лайков')}
        </div>
      </div>
    </div>
  )
}

function PublicStatsPanel({
  stats,
}: {
  stats: UserStatsResponse | null
}) {
  const { t } = useTranslation()
  const topTracks = stats?.top_tracks?.slice(0, 5) ?? []
  return (
    <section className="rp-public-stats">
      <div className="rp-public-stats__grid">
        <Metric
          icon="music"
          label={t('author.statsTracks', 'Треков')}
          value={formatCompact(stats?.total_tracks ?? 0)}
        />
        <Metric
          icon="headphones"
          label={t('author.statsPlays', 'Прослушиваний')}
          value={formatCompact(stats?.total_plays ?? 0)}
        />
        <Metric
          icon="heart"
          label={t('author.statsLikes', 'Лайков')}
          value={formatCompact(stats?.total_likes ?? 0)}
        />
        <Metric
          icon="users-following"
          label={t('author.statsFollowers', 'Подписчиков')}
          value={formatCompact(stats?.followers_count ?? 0)}
        />
      </div>

      <div className="rp-public-top">
        <h3 className="rp-public-top__title">
          {t('profile.public.topTracks', 'Популярные треки')}
        </h3>
        {topTracks.length > 0 ? (
          <div className="rp-public-top__list">
            {topTracks.map((track, index) => (
              <div
                key={track.id}
                className="rp-public-top__row"
              >
                <span className="rp-public-top__rank">
                  {index + 1}
                </span>
                <span className="rp-public-top__name">
                  {track.title}
                  {track.artist ? (
                    <small>{track.artist}</small>
                  ) : null}
                </span>
                <span className="rp-public-top__plays">
                  {formatCompact(track.play_count)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="rp-public-top__empty">
            {t(
              'profile.public.noTopTracks',
              'Пока недостаточно публичной статистики.',
            )}
          </p>
        )}
      </div>
    </section>
  )
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: string
  label: string
  value: string
}) {
  return (
    <div className="rp-public-metric">
      <span className="rp-public-metric__icon">
        <Icon name={icon} size={18} />
      </span>
      <span className="rp-public-metric__value">{value}</span>
      <span className="rp-public-metric__label">{label}</span>
    </div>
  )
}

function LoadMoreButton({
  loading,
  onClick,
}: {
  loading: boolean
  onClick: () => void
}) {
  const { t } = useTranslation()
  return (
    <MotionPress
      type="button"
      variant="ghost"
      haptic="light"
      className="rd-liked-more rp-public-load-more"
      onClick={onClick}
      disabled={loading}
    >
      {loading ? t('common.loading') : t('common.showMore')}
    </MotionPress>
  )
}

function formatCompact(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`
  }
  return String(value)
}
