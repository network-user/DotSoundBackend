import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { tg, userId } from '@/lib/telegram'
import type { Track, UserStatsResponse } from '@/types/api'
import { usePlayer } from '@/store/PlayerContext'
import { ProfileHero } from '@/components/Profile/ProfileHero'
import { ProfileStats } from '@/components/Profile/ProfileStats'
import { ProfileActions } from '@/components/Profile/ProfileActions'
import { ProfileTrackList } from '@/components/Profile/ProfileTrackList'
import { ImportView } from '@/components/Import/ImportView'

type ProfileTab = 'profile' | 'import'

interface Props {
  active: boolean
  onNavigate: (view: 'liked' | 'playlists' | 'upload') => void
}

export function ProfileView({ active, onNavigate }: Props) {
  const { playTrack } = usePlayer()
  const [tab, setTab] = useState<ProfileTab>('profile')
  const [stats, setStats] = useState<UserStatsResponse | null>(null)
  const [myTracks, setMyTracks] = useState<Track[]>([])
  const [editMode, setEditMode] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const tgUser = tg.initDataUnsafe?.user

  const defaultName = [tgUser?.first_name, tgUser?.last_name]
    .filter(Boolean).join(' ') || tgUser?.username || 'Пользователь'

  useEffect(() => {
    if (!active || !userId) return
    const id = userId

    api.getUserStats(id)
      .then(setStats)
      .catch(() => setStats({
        user_id: userId ?? 0,
        total_tracks: 0,
        total_plays: 0,
        total_likes: 0,
        followers_count: 0,
        following_count: 0,
        top_tracks: [],
      }))

    api.getUserProfile(id)
      .then((profile) => {
        setDisplayName(profile.display_name || defaultName)
        api.getAvatarUrl(id)
          .then(({ avatar_url }) => setAvatarSrc(avatar_url))
          .catch(() => {})
      })
      .catch(() => setDisplayName(defaultName))

    api.getMyTracks(id)
      .then((data) => setMyTracks(data.items))
      .catch(() => {})
  }, [active])

  const handleSave = async () => {
    if (!userId) return
    setSaving(true)
    try {
      if (displayName.trim()) {
        await api.updateProfile(displayName.trim())
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

  const currentAvatar = avatarSrc || tgUser?.photo_url || null
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
      <div className="profile-tabs">
        <button
          className={`profile-tab${tab === 'profile' ? ' active' : ''}`}
          onClick={() => setTab('profile')}
        >
          Профиль
        </button>
        <button
          className={`profile-tab${tab === 'import' ? ' active' : ''}`}
          onClick={() => setTab('import')}
        >
          Импорт
        </button>
      </div>

      {tab === 'profile' && (
        <>
          <ProfileHero
            currentAvatar={currentAvatar}
            shownName={shownName}
            username={tgUser.username}
            editMode={editMode}
            displayName={displayName}
            saving={saving}
            onEditStart={() => setEditMode(true)}
            onSave={handleSave}
            onCancel={() => setEditMode(false)}
            onDisplayNameChange={setDisplayName}
          />
          <ProfileStats stats={stats} />
          <ProfileActions onNavigate={onNavigate} />
          <ProfileTrackList
            tracks={myTracks}
            onPlay={playTrack}
            onToggleVisibility={handleToggleVisibility}
            onDelete={handleDelete}
          />
        </>
      )}

      {tab === 'import' && (
        <ImportView active={tab === 'import'} />
      )}
    </section>
  )
}
