import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import {
  getInternalUserId,
  tg,
} from '@/lib/telegram'
import type {
  Track,
  UserStatsResponse,
} from '@/types/api'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import { ProfileHero } from '@/components/Profile/ProfileHero'
import { ProfileStats } from '@/components/Profile/ProfileStats'
import { ProfileActions } from '@/components/Profile/ProfileActions'
import { ProfileTrackList } from '@/components/Profile/ProfileTrackList'
import { ImportView } from '@/components/Import/ImportView'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { ProfileAdminButton } from '@/components/Admin/ProfileAdminButton'

type ProfileTab = 'profile' | 'import'

interface Props {
  onOpenSettings?: () => void
}

export function ProfileView({
  onOpenSettings,
}: Props) {
  const { playTrack } = usePlayer()
  const [tab, setTab] =
    useState<ProfileTab>('profile')
  const [stats, setStats] =
    useState<UserStatsResponse | null>(null)
  const [myTracks, setMyTracks] = useState<Track[]>(
    [],
  )
  const [editMode, setEditMode] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState<
    string | undefined
  >(undefined)
  const [avatarSrc, setAvatarSrc] = useState<
    string | null
  >(null)
  const [saving, setSaving] = useState(false)
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<number>>(new Set())
  const deleteTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())

  const tgUser = tg.initDataUnsafe?.user

  useEffect(() => {
    const internalId = getInternalUserId()
    if (!internalId) return

    api
      .getUserStats(internalId)
      .then(setStats)
      .catch(() =>
        setStats({
          user_id: internalId,
          total_tracks: 0,
          total_plays: 0,
          total_likes: 0,
          followers_count: 0,
          following_count: 0,
          top_tracks: [],
        }),
      )

    api
      .getUserProfile(internalId)
      .then((profile) => {
        const name =
          profile.display_name ||
          [
            profile.first_name,
            profile.last_name,
          ]
            .filter(Boolean)
            .join(' ') ||
          tgUser?.first_name ||
          'Пользователь'
        setDisplayName(name)
        setUsername(
          profile.username ||
            tgUser?.username ||
            undefined,
        )
        api
          .getAvatarUrl(internalId)
          .then(({ avatar_url }) =>
            setAvatarSrc(avatar_url),
          )
          .catch(() => {})
      })
      .catch(() =>
        setDisplayName(
          tgUser?.first_name || 'Пользователь',
        ),
      )

    api
      .getMyLibrary()
      .then((data) => setMyTracks(data.items))
      .catch(() => {})
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      if (displayName.trim()) {
        await api.updateProfile(displayName.trim())
      }
      setEditMode(false)
    } catch {} finally {
      setSaving(false)
    }
  }

  const handleToggleVisibility = async (
    track: Track,
  ) => {
    try {
      const updated = await api.updateTrack(
        track.id,
        { is_public: !track.is_public },
      )
      setMyTracks((prev) =>
        prev.map((t) =>
          t.id === updated.id ? updated : t,
        ),
      )
    } catch {}
  }

  const handleDelete = async (track: Track) => {
    if (!pendingDeleteIds.has(track.id)) {
      setPendingDeleteIds((prev) => new Set([...prev, track.id]))
      const t = setTimeout(() => {
        setPendingDeleteIds((prev) => {
          const n = new Set(prev)
          n.delete(track.id)
          return n
        })
        deleteTimers.current.delete(track.id)
      }, 3000)
      deleteTimers.current.set(track.id, t)
      return
    }
    const timer = deleteTimers.current.get(track.id)
    if (timer) clearTimeout(timer)
    deleteTimers.current.delete(track.id)
    setPendingDeleteIds((prev) => {
      const n = new Set(prev)
      n.delete(track.id)
      return n
    })
    try {
      await api.deleteTrack(track.id)
      setMyTracks((prev) =>
        prev.filter((t) => t.id !== track.id),
      )
    } catch {}
  }

  const currentAvatar =
    avatarSrc || tgUser?.photo_url || null
  const shownName = displayName || 'Пользователь'

  return (
    <section
      id="view-profile"
      className="view active"
    >
      <div className="profile-tabs-row">
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
        <div className="profile-header-actions">
          <NotificationBell />
          <ProfileAdminButton />
          {onOpenSettings && (
            <button
              className="icon-btn profile-settings-btn"
              onClick={onOpenSettings}
            >
              <Icon name="settings" size={20} />
            </button>
          )}
        </div>
      </div>

      {tab === 'profile' && (
        <>
          <ProfileHero
            currentAvatar={currentAvatar}
            shownName={shownName}
            username={username}
            editMode={editMode}
            displayName={displayName}
            saving={saving}
            onEditStart={() => setEditMode(true)}
            onSave={handleSave}
            onCancel={() => setEditMode(false)}
            onDisplayNameChange={setDisplayName}
          />
          <ProfileStats stats={stats} />
          <ProfileActions />
          <ProfileTrackList
            tracks={myTracks}
            onPlay={playTrack}
            onToggleVisibility={
              handleToggleVisibility
            }
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
