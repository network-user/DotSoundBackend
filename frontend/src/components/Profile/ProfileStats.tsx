import { formatPlays } from '@/lib/utils'
import type { UserStatsResponse } from '@/types/api'

interface Props {
  stats: UserStatsResponse | null
}

export function ProfileStats({ stats }: Props) {
  return (
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
  )
}
