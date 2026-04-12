import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { TrackList } from '@/components/TrackList/TrackList'
import type { AuthorProfile, Track, UserStatsResponse } from '@/types/api'

interface Props {
  authorId: number | null
  onClose: () => void
}

export function AuthorView({ authorId, onClose }: Props) {
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
    if (!authorId) return
    setFollowLoading(true)
    try {
      const res = await api.toggleFollow(authorId)
      setFollowing(res.following)
      // Refresh stats for follower count
      api.getUserStats(authorId).then(setStats).catch(() => {})
    } catch {}
    setFollowLoading(false)
  }

  if (!authorId) return null

  return (
    <div className="author-view">
      {/* Header */}
      <div className="author-view-header">
        <button className="author-back-btn icon-btn" onClick={onClose}>
          ‹ Назад
        </button>
      </div>

      {loading ? (
        <div className="loader" style={{ marginTop: 48 }} />
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
                '👤'
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
              <button
                className={`author-follow-btn${following ? ' following' : ''}`}
                onClick={handleFollow}
                disabled={followLoading}
              >
                {followLoading
                  ? '...'
                  : following
                    ? '✓ Подписан'
                    : '+ Подписаться'}
              </button>
            )}
          </div>

          {/* Stats */}
          {stats && (
            <div className="profile-stats">
              <div className="stat-item">
                <div className="stat-value">{stats.total_tracks}</div>
                <div className="stat-label">Треков</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{fmtCount(stats.total_plays)}</div>
                <div className="stat-label">Прослушиваний</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{fmtCount(stats.followers_count ?? 0)}</div>
                <div className="stat-label">Подписчиков</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{fmtCount(stats.total_likes)}</div>
                <div className="stat-label">Лайков</div>
              </div>
            </div>
          )}

          {/* Track list */}
          <div className="section-header" style={{ marginTop: 20 }}>
            <span className="section-title">Треки · {tracksTotal}</span>
          </div>
          <TrackList tracks={tracks} />
          {tracks.length === 0 && !loading && (
            <p className="empty-hint">Нет публичных треков</p>
          )}
        </>
      ) : (
        <p className="empty-hint">Автор не найден</p>
      )}
    </div>
  )
}

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
