import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { api } from '@/lib/api'
import { tg, userId } from '@/lib/telegram'
import type { Track, UserStatsResponse } from '@/types/api'
import { usePlayer } from '@/store/PlayerContext'

interface Props {
  active: boolean
  onNavigate: (view: 'liked' | 'playlists' | 'upload') => void
}

export function ProfileView({ active, onNavigate }: Props) {
  const { playTrack } = usePlayer()
  const [stats, setStats] = useState<UserStatsResponse | null>(null)
  const [myTracks, setMyTracks] = useState<Track[]>([])
  const [editMode, setEditMode] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null)
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const avatarInputRef = useRef<HTMLInputElement>(null)

  const tgUser = tg.initDataUnsafe?.user

  const defaultName = [tgUser?.first_name, tgUser?.last_name]
    .filter(Boolean).join(' ') || tgUser?.username || 'Пользователь'

  useEffect(() => {
    if (!active || !userId) return

    api.getUserStats(userId)
      .then(setStats)
      .catch(() => setStats({ total_tracks: 0, total_plays: 0, total_likes: 0 }))

    api.getUserProfile(userId)
      .then((profile) => {
        setDisplayName(profile.display_name || defaultName)
        if (profile.avatar_key) {
          api.getAvatarUrl(userId)
            .then(({ avatar_url }) => setAvatarSrc(avatar_url))
            .catch(() => {})
        }
      })
      .catch(() => setDisplayName(defaultName))

    api.getMyTracks(userId)
      .then((data) => setMyTracks(data.items))
      .catch(() => {})
  }, [active])

  const handleAvatarChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null
    setAvatarFile(file)
    if (file) {
      const reader = new FileReader()
      reader.onload = (ev) => setAvatarPreview(ev.target?.result as string)
      reader.readAsDataURL(file)
    }
  }

  const handleSave = async () => {
    if (!userId) return
    setSaving(true)
    try {
      if (displayName.trim()) {
        await api.updateProfile(userId, displayName.trim())
      }
      if (avatarFile) {
        const fd = new FormData()
        fd.append('avatar', avatarFile)
        const { avatar_url } = await api.uploadAvatar(userId, fd)
        setAvatarSrc(avatar_url)
        setAvatarFile(null)
        setAvatarPreview(null)
      }
      setEditMode(false)
    } catch { } finally {
      setSaving(false)
    }
  }

  const handleToggleVisibility = async (track: Track) => {
    if (!userId) return
    try {
      const updated = await api.updateTrack(
        track.id,
        { is_public: !track.is_public },
        userId,
      )
      setMyTracks((prev) => prev.map((t) => t.id === updated.id ? updated : t))
    } catch { }
  }

  const handleDelete = async (track: Track) => {
    if (!userId) return
    if (!confirm(`Удалить "${track.title}"?`)) return
    try {
      await api.deleteTrack(track.id, userId)
      setMyTracks((prev) => prev.filter((t) => t.id !== track.id))
    } catch { }
  }

  const currentAvatar = avatarPreview || avatarSrc || tgUser?.photo_url || null
  const shownName = displayName || defaultName

  if (!tgUser) {
    return (
      <section id="view-profile" className={`view${active ? ' active' : ''}`}>
        <div className="view-header"><h2>Профиль</h2></div>
        <p className="empty-hint">
          <strong>Нет данных</strong>
          Открой приложение через Telegram
        </p>
      </section>
    )
  }

  return (
    <section id="view-profile" className={`view${active ? ' active' : ''}`}>
      <div className="profile-hero">
        <div
          className={`profile-avatar${editMode ? ' editable' : ''}`}
          onClick={() => editMode && avatarInputRef.current?.click()}
        >
          {currentAvatar
            ? <img src={currentAvatar} alt={shownName} />
            : shownName.charAt(0).toUpperCase()
          }
          {editMode && <span className="avatar-edit-hint">✎</span>}
        </div>
        <input
          ref={avatarInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={handleAvatarChange}
        />

        {editMode ? (
          <input
            className="form-input profile-name-input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={128}
            placeholder="Отображаемое имя"
          />
        ) : (
          <div className="profile-name">{shownName}</div>
        )}

        {tgUser.username && !editMode && (
          <div className="profile-username">@{tgUser.username}</div>
        )}

        <div className="profile-edit-controls">
          {!editMode ? (
            <button className="profile-edit-btn" onClick={() => setEditMode(true)}>
              ✎ Изменить
            </button>
          ) : (
            <>
              <button className="btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Сохранение…' : 'Сохранить'}
              </button>
              <button className="profile-edit-cancel" onClick={() => {
                setEditMode(false)
                setAvatarFile(null)
                setAvatarPreview(null)
              }}>
                Отмена
              </button>
            </>
          )}
        </div>
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

      {myTracks.length > 0 && (
        <div className="my-tracks-section">
          <p className="my-tracks-label">Мои треки</p>
          {myTracks.map((track) => (
            <div key={track.id} className="my-track-row" onClick={() => playTrack(track)}>
              <div className="my-track-info">
                <span className="my-track-title">{track.title}</span>
                {track.source === 'soundcloud' && (
                  <span className="track-badge track-badge-sc">SC</span>
                )}
                {!track.is_public && (
                  <span className="track-badge track-badge-private">🔒</span>
                )}
              </div>
              <div className="my-track-actions" onClick={(e) => e.stopPropagation()}>
                <button
                  className="icon-btn"
                  title={track.is_public ? 'Сделать приватным' : 'Сделать публичным'}
                  onClick={() => handleToggleVisibility(track)}
                >
                  {track.is_public ? '👁' : '🔒'}
                </button>
                <button
                  className="icon-btn"
                  title="Удалить"
                  onClick={() => handleDelete(track)}
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function formatPlays(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
