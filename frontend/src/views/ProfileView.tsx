import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { api } from '@/lib/api'
import { tg, userId } from '@/lib/telegram'
import type { Track, UserStatsResponse } from '@/types/api'
import { usePlayer } from '@/store/PlayerContext'
import { ProfileHero } from '@/components/Profile/ProfileHero'
import { ProfileStats } from '@/components/Profile/ProfileStats'
import { ProfileActions } from '@/components/Profile/ProfileActions'
import { ProfileTrackList } from '@/components/Profile/ProfileTrackList'

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
    const id = userId

    api.getUserStats(id)
      .then(setStats)
      .catch(() => setStats({ total_tracks: 0, total_plays: 0, total_likes: 0 }))

    api.getUserProfile(id)
      .then((profile) => {
        setDisplayName(profile.display_name || defaultName)
        if (profile.avatar_key) {
          api.getAvatarUrl(id)
            .then(({ avatar_url }) => setAvatarSrc(avatar_url))
            .catch(() => {})
        }
      })
      .catch(() => setDisplayName(defaultName))

    api.getMyTracks(id)
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
      <ProfileHero
        currentAvatar={currentAvatar}
        shownName={shownName}
        username={tgUser.username}
        editMode={editMode}
        displayName={displayName}
        saving={saving}
        avatarInputRef={avatarInputRef}
        onEditStart={() => setEditMode(true)}
        onSave={handleSave}
        onCancel={() => {
          setEditMode(false)
          setAvatarFile(null)
          setAvatarPreview(null)
        }}
        onDisplayNameChange={setDisplayName}
        onAvatarChange={handleAvatarChange}
      />
      <ProfileStats stats={stats} />
      <ProfileActions onNavigate={onNavigate} />
      <ProfileTrackList
        tracks={myTracks}
        onPlay={playTrack}
        onToggleVisibility={handleToggleVisibility}
        onDelete={handleDelete}
      />
    </section>
  )
}
