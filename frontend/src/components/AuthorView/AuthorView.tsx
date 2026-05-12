import {
  useCallback,
  useEffect,
  useState,
} from 'react'
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
import { showIsland } from '@/lib/island'
import { queueMutation } from '@/lib/pendingEvents'
import { copyToClipboard } from '@/lib/platform'
import { ProfileShareModal } from '@/components/Profile/ProfileShareModal'
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
  const [author, setAuthor] = useState<AuthorProfile | null>(null)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [stats, setStats] = useState<UserStatsResponse | null>(null)
  const [tracks, setTracks] = useState<Track[]>([])
  const [tracksTotal, setTracksTotal] = useState(0)
  const [following, setFollowing] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)
  const [followLoading, setFollowLoading] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [shareOpen, setShareOpen] = useState(false)
  const [shareInitialTab, setShareInitialTab] = useState<
    'link' | 'qr' | 'card'
  >('link')

  const internalId = getInternalUserId()
  const isOwnProfile = internalId !== null && author?.id === internalId

  const loadAuthor = useCallback(async () => {
    if (!authorId) return
    setLoading(true)
    setAuthor(null)
    setStats(null)
    setTracks([])
    setTracksTotal(0)
    setFollowing(null)
    try {
      const profile = await api.getAuthorProfile(authorId)
      setAuthor(profile as AuthorProfile)
      const limited = profile.profile_access === 'limited'
      const avatarRes = await api.getAvatarUrl(authorId)
      setAvatarUrl(avatarRes.avatar_url)
      const followRes =
        internalId
          ? await api.getFollowStatus(authorId).catch(() => null)
          : null
      if (followRes) setFollowing(followRes.following)
      if (limited) {
        return
      }
      const [authorStats, tracksRes] = await Promise.all([
        api.getUserStats(authorId),
        api.getAuthorTracks(authorId, 1, 20),
      ])
      setStats(authorStats)
      setTracks(tracksRes.items)
      setTracksTotal(tracksRes.total)
    } catch {
      setAuthor(null)
    } finally {
      setLoading(false)
    }
  }, [authorId, internalId])

  useEffect(() => {
    void loadAuthor()
  }, [loadAuthor, reloadKey])

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
        followers_count: Math.max(
          0,
          (stats.followers_count ?? 0) + delta,
        ),
      })
    }
    haptic('light')
    setFollowLoading(true)
    try {
      await api.toggleFollow(authorId)
      setReloadKey((k) => k + 1)
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
      showIsland({
        kind: 'error',
        title: getApiErrorMessage(
          e,
          t('artist.follow_failed', 'Не удалось обновить подписку'),
        ),
        durationMs: 4000,
      })
    }
    setFollowLoading(false)
  }

  const handleCopyProfileLink = async () => {
    if (!authorId) return
    try {
      const card = await api.getProfileShareCard(authorId)
      const url = card.deep_link || card.profile_url
      const ok = await copyToClipboard(url)
      showIsland({
        kind: ok ? 'toast' : 'error',
        title: ok
          ? t('profile.share.copied', 'Ссылка скопирована')
          : t('profile.share.copyFail', 'Не удалось скопировать'),
        iconName: ok ? 'check' : 'alert-triangle',
        durationMs: 2200,
      })
    } catch {
      showIsland({
        kind: 'error',
        title: t(
          'author.shareUnavailable',
          'Ссылка недоступна для этого профиля',
        ),
        iconName: 'alert-triangle',
        durationMs: 3500,
      })
    }
  }

  const openShareQr = () => {
    setShareInitialTab('qr')
    setShareOpen(true)
  }

  if (!authorId) return null

  const canShare = Boolean(
    author && author.profile_access === 'full',
  )

  return (
    <div className="author-view">
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
        {canShare && (
          <div className="author-header-actions">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="author-header-icon-btn icon-btn"
              aria-label={t(
                'author.copyProfileLink',
                'Копировать ссылку',
              )}
              onClick={() => {
                haptic('light')
                void handleCopyProfileLink()
              }}
            >
              <Icon name="copy" size={18} />
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="author-header-icon-btn icon-btn"
              aria-label={t('profile.share.tabQr', 'QR')}
              onClick={() => {
                haptic('light')
                openShareQr()
              }}
            >
              <Icon name="share-arrow" size={18} />
            </MotionPress>
          </div>
        )}
      </div>

      {loading ? (
        <div className="loader author-loader" />
      ) : author ? (
        <>
          <div className="author-hero">
            <div className="author-avatar">
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt=""
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
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

            {author.profile_access === 'limited' && (
              <p className="author-privacy-hint">
                {author.profile_visibility === 'followers_only'
                  ? t(
                      'author.profileFollowersOnly',
                      'Полный профиль, треки и подписки '
                        + 'видны только подписчикам.',
                    )
                  : t(
                      'author.profileHidden',
                      'Пользователь скрыл расширенный профиль.',
                    )}
              </p>
            )}

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
                <div className="stat-value">
                  {fmtCount(stats.followers_count ?? 0)}
                </div>
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

          <div className="section-header author-section-header">
            <span className="section-title">
              {t('author.tracksTitle', 'Треки')} · {tracksTotal}
            </span>
          </div>
          <TrackList tracks={tracks} />
          {tracks.length === 0 && !loading && (
            <p className="empty-hint">
              {author.profile_access === 'limited'
                ? t(
                    'author.tracksLocked',
                    'Треки скрыты настройками приватности.',
                  )
                : t(
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

      {authorId ? (
        <ProfileShareModal
          open={shareOpen}
          userId={authorId}
          initialTab={shareInitialTab}
          onClose={() => setShareOpen(false)}
        />
      ) : null}
    </div>
  )
}

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
