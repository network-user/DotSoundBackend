import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { tg, userId } from '@/lib/telegram'
import type { UserStatsResponse } from '@/types/api'

interface Props {
  active: boolean
  onNavigate: (view: 'liked' | 'playlists' | 'upload') => void
}

export function ProfileView({ active, onNavigate }: Props) {
  const [stats, setStats] = useState<UserStatsResponse | null>(null)

  const tgUser = tg.initDataUnsafe?.user

  useEffect(() => {
    if (!active || !userId) return
    api.getUserStats(userId)
      .then(setStats)
      .catch(() => setStats({ total_tracks: 0, total_plays: 0, total_likes: 0 }))
  }, [active])

  if (!tgUser) {
    return (
      <section id="view-profile" className={`view${active ? ' active' : ''}`}>
        <div className="view-header">
          <h2>Профиль</h2>
        </div>
        <p className="empty-hint">
          <strong>Нет данных</strong>
          Открой приложение через Telegram
        </p>
      </section>
    )
  }

  const displayName = [tgUser.first_name, tgUser.last_name].filter(Boolean).join(' ')
    || tgUser.username
    || 'Пользователь'

  return (
    <section id="view-profile" className={`view${active ? ' active' : ''}`}>
      <div className="profile-hero">
        <div className="profile-avatar">
          {tgUser.photo_url
            ? <img src={tgUser.photo_url} alt={displayName} />
            : displayName.charAt(0).toUpperCase()
          }
        </div>
        <div className="profile-name">{displayName}</div>
        {tgUser.username && (
          <div className="profile-username">@{tgUser.username}</div>
        )}
      </div>

      <div className="profile-stats">
        <div className="stat-item">
          <div className="stat-value">{stats?.total_tracks ?? '—'}</div>
          <div className="stat-label">Треков</div>
        </div>
        <div className="stat-item">
          <div className="stat-value">
            {stats ? formatPlays(stats.total_plays) : '—'}
          </div>
          <div className="stat-label">Прослушиваний</div>
        </div>
        <div className="stat-item">
          <div className="stat-value">{stats?.total_likes ?? '—'}</div>
          <div className="stat-label">Лайков</div>
        </div>
      </div>

      <div className="profile-actions">
        <button
          id="profile-action-upload"
          className="profile-action-btn"
          onClick={() => onNavigate('upload')}
        >
          <span className="profile-action-icon">↑</span>
          <span className="profile-action-label">Загрузить трек</span>
          <span className="profile-action-chevron">›</span>
        </button>

        <button
          id="profile-action-playlists"
          className="profile-action-btn"
          onClick={() => onNavigate('playlists')}
        >
          <span className="profile-action-icon">▤</span>
          <span className="profile-action-label">Мои плейлисты</span>
          <span className="profile-action-chevron">›</span>
        </button>

        <button
          id="profile-action-liked"
          className="profile-action-btn"
          onClick={() => onNavigate('liked')}
        >
          <span className="profile-action-icon">♥</span>
          <span className="profile-action-label">Понравившееся</span>
          <span className="profile-action-chevron">›</span>
        </button>
      </div>
    </section>
  )
}

function formatPlays(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
