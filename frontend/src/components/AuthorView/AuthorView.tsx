import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, getApiErrorMessage } from '@/lib/api'
import {
  getInternalUserId,
  haptic,
  hapticNotification,
} from '@/lib/telegram'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useToast } from '@/components/ui/Toast'
import { queueMutation } from '@/lib/pendingEvents'
import type { AuthorProfile, Track, UserStatsResponse } from '@/types/api'

function _isNetworkError(e: unknown): boolean {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return true
  }
  return (
    e instanceof TypeError &&
    typeof e.message === 'string' &&
    /fetch|network/i.test(e.message)
  )
}

interface Props {
  authorId: number | null
  onClose: () => void
}

export function AuthorView({ authorId, onClose }: Props) {
  const { t } = useTranslation()
  const toast = useToast()
  const [author, setAuthor] = useState<AuthorProfile | null>(null)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [stats, setStats] = useState<UserStatsResponse | null>(null)
  const [tracks, setTracks] = useState<Track[]>([])
  const [tracksTotal, setTracksTotal] = useState(0)
  const [following, setFollowing] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)
  const [followLoading, setFollowLoading] = useState(false)

  const internalId = getInternalUserId()
  const isOwnProfile = internalId !== null && author?.id === internalId

  useEffect(() => {
    if (!authorId) return
    setLoading(true)
    setAuthor(null)
    setStats(null)
    setTracks([])
    setFollowing(null)

    Promise.all([
      api.getAuthorProfile(authorId),
      api.getUserStats(authorId),
      api.getAuthorTracks(authorId, 1, 20),
      api.getAvatarUrl(authorId),
      internalId ? api.getFollowStatus(authorId).catch(() => null) : Promise.resolve(null),
    ])
      .then(([profile, authorStats, tracksRes, avatarRes, followRes]) => {
        setAuthor(profile as AuthorProfile)
        setStats(authorStats)
        setTracks(tracksRes.items)
        setTracksTotal(tracksRes.total)
        setAvatarUrl(avatarRes.avatar_url)
        if (followRes) setFollowing(followRes.following)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [authorId])

  const handleFollow = async () => {
    if (!authorId || followLoading) return
    const prevFollowing = following
    const prevStats = stats
    const willFollow = !(prevFollowing === true)
    setFollowing(willFollow)
    if (stats) {
      const delta = willFollow ? 1 : -1
      setStats({
        ...stats,
        followers_count: Math.max(0, (stats.followers_count ?? 0) + delta),
      })
    }
    haptic('light')
    setFollowLoading(true)
    try {
      const res = await api.toggleFollow(authorId)
      setFollowing(res.following)
      api.getUserStats(authorId).then(setStats).catch(() => {})
    } catch (e) {
      if (_isNetworkError(e)) {
        await queueMutation(
          'POST',
          `/api/v1/users/${authorId}/follow`,
        )
        setFollowLoading(false)
        return
      }
      setFollowing(prevFollowing)
      setStats(prevStats)
      hapticNotification('error')
      const msg = getApiErrorMessage(
        e,
        t('artist.follow_failed', 'Не удалось обновить подписку'),
      )
      toast.error(msg)
    }
    setFollowLoading(false)
  }

  if (!authorId) return null

  return (
    <div className="author-view">
      {/* Header */}
      <div className="author-view-header">
        <MotionPress
          type="button"
          variant="ghost"
          haptic="light"
          className="author-back-btn icon-btn"
          onClick={onClose}
        >
          <Icon name="chevron" size={18} />
          {t('common.back', { defaultValue: 'Назад' })}
        </MotionPress>
      </div>

      {loading ? (
        <div className="loader author-loader" />
      ) : author ? (
        <>
          {/* Hero */}
          <div className="author-hero">
            <div className="author-avatar">
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt=""
                  onError={(e) => { e.currentTarget.style.display = 'none' }}
                />
              ) : (
                <Icon name="user" size={28} />
              )}
            </div>
            <h2 className="author-name">
              {author.display_name || author.username || 'Автор'}
            </h2>
            {author.username && (
              <p className="author-username">@{author.username}</p>
            )}

            {/* Follow button (hide for own profile) */}
            {!isOwnProfile && internalId && (
              <MotionPress
                type="button"
                variant={following ? 'subtle' : 'primary'}
                haptic="medium"
                className={`author-follow-btn${following ? ' following' : ''}`}
                onClick={handleFollow}
                disabled={followLoading}
              >
                <Icon
                  name={following ? 'check' : 'bell'}
                  size={14}
                />
                {followLoading
                  ? '...'
                  : following
                    ? t('artist.following', {
                        defaultValue: 'Подписан',
                      })
                    : t('artist.follow', {
                        defaultValue: 'Подписаться',
                      })}
              </MotionPress>
            )}
          </div>

          {/* Stats */}
          {stats && (
            <div className="profile-stats">
              <div className="stat-item">
                <div className="stat-value">{stats.total_tracks}</div>
                <div className="stat-label">
                  {t('author.statsTracks', 'Треков')}
                </div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{fmtCount(stats.total_plays)}</div>
                <div className="stat-label">
                  {t('author.statsPlays', 'Прослушиваний')}
                </div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{fmtCount(stats.followers_count ?? 0)}</div>
                <div className="stat-label">
                  {t('author.statsFollowers', 'Подписчиков')}
                </div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{fmtCount(stats.total_likes)}</div>
                <div className="stat-label">
                  {t('author.statsLikes', 'Лайков')}
                </div>
              </div>
            </div>
          )}

          {/* Track list */}
          <div className="section-header author-section-header">
            <span className="section-title">
              {t('author.tracksTitle', 'Треки')} · {tracksTotal}
            </span>
          </div>
          <TrackList tracks={tracks} />
          {tracks.length === 0 && !loading && (
            <p className="empty-hint">
              {t(
                'author.emptyTracks',
                'Нет публичных треков',
              )}
            </p>
          )}
        </>
      ) : (
        <p className="empty-hint">
          {t('author.notFound', 'Автор не найден')}
        </p>
      )}
    </div>
  )
}

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
