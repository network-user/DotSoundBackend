import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import {
  getInternalUserId,
  hapticNotification,
  hapticSelection,
  tg,
} from '@/lib/telegram'
import { useSound } from '@/store/SoundContext'
import type {
  Track,
  UserStatsResponse,
} from '@/types/api'
import { usePlayerActions } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import { showIsland } from '@/lib/island'
import { MotionPress } from '@/components/ui/MotionPress'
import { ProfileHero } from '@/components/Profile/ProfileHero'
import { ProfileShareModal } from '@/components/Profile/ProfileShareModal'
import {
  extractCoverPalette,
  type CoverPalette,
} from '@/lib/coverPalette'
import { ProfileStats } from '@/components/Profile/ProfileStats'
import { ListenerStats } from '@/components/Profile/ListenerStats'
import { ProfileActions } from '@/components/Profile/ProfileActions'
import { ArtistProfileCard } from '@/components/Profile/ArtistProfileCard'
import { ProfileUploadCallout } from '@/components/Profile/ProfileUploadCallout'
import { ProfileTrackList } from '@/components/Profile/ProfileTrackList'
import { ImportView } from '@/components/Import/ImportView'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { UploadQueueBadge } from '@/components/Upload/UploadQueueBadge'
import { ProfileAdminButton } from '@/components/Admin/ProfileAdminButton'
import { ProfileDebugMenu } from '@/components/Admin/ProfileDebugMenu'
import { MyComplaintsList } from '@/components/Profile/MyComplaintsList'
import { ProfileStatsTab } from '@/components/Profile/ProfileStatsTab'
import { DislikedView } from '@/views/DislikedView'

import '@/styles/redesign-profile.css'
import '@/styles/redesign-track-edit.css'

const PROFILE_COLLECTION_PAGE_SIZE = 30

type ProfileTab =
  | 'profile'
  | 'import'
  | 'complaints'
  | 'dislikes'
  | 'stats'

interface Props {
  onOpenSettings?: () => void
}

export function ProfileView({
  onOpenSettings,
}: Props) {
  const { t } = useTranslation()
  const { playTrack } = usePlayerActions()
  const sound = useSound()
  const fallbackName = t(
    'redesign.library.profileNameFallback',
  )
  const [tab, setTab] =
    useState<ProfileTab>('profile')
  const [navDirection, setNavDirection] = useState<
    'forward' | 'back'
  >('forward')
  const goTab = (next: ProfileTab) => {
    setNavDirection(next === 'profile' ? 'back' : 'forward')
    setTab(next)
  }
  const [stats, setStats] =
    useState<UserStatsResponse | null>(null)
  const [myTracks, setMyTracks] = useState<Track[]>(
    [],
  )
  const [myTracksHasMore, setMyTracksHasMore] = useState(false)
  const [myTracksLoadingMore, setMyTracksLoadingMore] = useState(false)
  const myTracksPageRef = useRef(1)
  const [editMode, setEditMode] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState<
    string | undefined
  >(undefined)
  const [avatarSrc, setAvatarSrc] = useState<
    string | null
  >(null)
  const [saving, setSaving] = useState(false)
  const pendingBlobUrlRef =
    useRef<string | null>(null)
  const displayNameBaselineRef =
    useRef('')
  const [pendingAvatarPreview, setPendingAvatarPreview] =
    useState<string | null>(null)
  const [pendingAvatarFile, setPendingAvatarFile] =
    useState<File | null>(null)
  const [palette, setPalette] = useState<CoverPalette | null>(null)
  const [shareOpen, setShareOpen] = useState(false)
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<number>>(new Set())
  const deleteTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())
  const [serverDebug, setServerDebug] = useState(false)

  const tgUser = tg.initDataUnsafe?.user
  const tgFirstName = tgUser?.first_name
  const tgUsername = tgUser?.username

  const loadMyTracksPage = useCallback(
    async (page: number, reset: boolean) => {
      if (reset) {
        setMyTracks([])
        setMyTracksHasMore(false)
      } else {
        setMyTracksLoadingMore(true)
      }
      try {
        const data = await api.getMyCollection(
          page,
          PROFILE_COLLECTION_PAGE_SIZE,
        )
        setMyTracks((prev) =>
          reset ? data.items : [...prev, ...data.items],
        )
        setMyTracksHasMore(
          data.total > page * PROFILE_COLLECTION_PAGE_SIZE,
        )
        myTracksPageRef.current = page
      } catch {
        if (reset) setMyTracks([])
        setMyTracksHasMore(false)
      } finally {
        if (!reset) setMyTracksLoadingMore(false)
      }
    },
    [],
  )

  const refreshProfileData = useCallback(() => {
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

    myTracksPageRef.current = 1
    void loadMyTracksPage(1, true)
  }, [loadMyTracksPage])

  const loadMoreMyTracks = useCallback(() => {
    if (myTracksLoadingMore || !myTracksHasMore) return
    void loadMyTracksPage(myTracksPageRef.current + 1, false)
  }, [
    loadMyTracksPage,
    myTracksHasMore,
    myTracksLoadingMore,
  ])

  useEffect(
    () => () => {
      if (pendingBlobUrlRef.current) {
        URL.revokeObjectURL(
          pendingBlobUrlRef.current,
        )
        pendingBlobUrlRef.current = null
      }
    },
    [],
  )

  useEffect(() => {
    api
      .getAuthConfig()
      .then(c => setServerDebug(Boolean(c.debug)))
      .catch(() => setServerDebug(false))
  }, [])

  useEffect(() => {
    refreshProfileData()

    const internalId = getInternalUserId()
    if (!internalId) return
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
          tgFirstName ||
          fallbackName
        setDisplayName(name)
        setUsername(
          profile.username ||
            tgUsername ||
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
          tgFirstName || fallbackName,
        ),
      )
  }, [fallbackName, refreshProfileData, tgFirstName, tgUsername])

  useEffect(() => {
    if (tab === 'profile') {
      refreshProfileData()
    }
  }, [refreshProfileData, tab])

  const clearPendingAvatar = () => {
    if (pendingBlobUrlRef.current) {
      URL.revokeObjectURL(
        pendingBlobUrlRef.current,
      )
      pendingBlobUrlRef.current = null
    }
    setPendingAvatarPreview(null)
    setPendingAvatarFile(null)
  }

  const handleAvatarFileChosen = (
    file: File,
  ) => {
    if (pendingBlobUrlRef.current) {
      URL.revokeObjectURL(
        pendingBlobUrlRef.current,
      )
    }
    const url = URL.createObjectURL(file)
    pendingBlobUrlRef.current = url
    setPendingAvatarPreview(url)
    setPendingAvatarFile(file)
  }

  const handleAvatarRejected = (
    reason: 'type' | 'size',
  ) => {
    const key =
      reason === 'size'
        ? 'redesign.library.profileAvatarTooLarge'
        : 'redesign.library.profileAvatarInvalidType'
    showIsland({
      kind: 'error',
      title: t(key),
      iconName: 'alert-triangle',
      durationMs: 4000,
    })
  }

  const handleEditStart = () => {
    displayNameBaselineRef.current = displayName
    setEditMode(true)
  }

  const handleCancelEdit = () => {
    setDisplayName(
      displayNameBaselineRef.current,
    )
    clearPendingAvatar()
    setEditMode(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (pendingAvatarFile) {
        const fd = new FormData()
        fd.append(
          'avatar',
          pendingAvatarFile,
        )
        try {
          const { avatar_url } =
            await api.uploadAvatar(fd)
          setAvatarSrc(avatar_url)
          clearPendingAvatar()
        } catch {
          showIsland({
            kind: 'error',
            title: t(
              'redesign.library.profileAvatarUploadFail',
            ),
            iconName: 'alert-triangle',
            durationMs: 4000,
          })
          setSaving(false)
          return
        }
      }
      if (displayName.trim()) {
        await api.updateProfile(displayName.trim())
      }
      hapticNotification('success')
      setEditMode(false)
    } catch {
      showIsland({
        kind: 'error',
        title: t(
          'redesign.library.profileSaveFail',
        ),
        iconName: 'alert-triangle',
        durationMs: 4000,
      })
    } finally {
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

  const currentAvatarRemote =
    avatarSrc || tgUser?.photo_url || null
  const heroAvatarImage =
    pendingAvatarPreview ||
    currentAvatarRemote ||
    null

  useEffect(() => {
    if (!heroAvatarImage) {
      setPalette(null)
      return
    }
    let cancelled = false
    extractCoverPalette(heroAvatarImage)
      .then((p) => {
        if (!cancelled) setPalette(p)
      })
      .catch(() => {
        if (!cancelled) setPalette(null)
      })
    return () => {
      cancelled = true
    }
  }, [heroAvatarImage])

  const shownName = displayName || fallbackName
  const feedbackTap = () => {
    hapticSelection()
    sound.play('tapSoft')
  }

  const subviewTitle = useMemo(() => {
    switch (tab) {
      case 'import':
        return t('profile.tabImport')
      case 'complaints':
        return t('profile.tabComplaints')
      case 'dislikes':
        return t('profile.tabDislikes')
      case 'stats':
        return t('profile.tabStats', 'Статистика')
      default:
        return ''
    }
  }, [tab, t])

  const isMainTab = tab === 'profile'

  return (
    <section
      id="view-profile"
      className="view active"
    >
      <header
        className={`profile-page-header${
          isMainTab ? '' : ' profile-page-header--sub'
        }`}
      >
        {isMainTab ? (
          <>
            <h1 className="profile-page-title">
              {t('profile.title')}
            </h1>
            <div className="profile-header-actions">
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t(
                  'profile.share.open',
                  'Поделиться профилем',
                )}
                onClick={() => {
                  feedbackTap()
                  setShareOpen(true)
                }}
              >
                <Icon name="share" size={20} />
              </MotionPress>
              <UploadQueueBadge />
              <NotificationBell />
              <ProfileAdminButton />
              <ProfileDebugMenu
                serverDebug={serverDebug}
              />
              {onOpenSettings && (
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="light"
                  className="icon-btn profile-settings-btn"
                  ariaLabel={t(
                    'profile.openSettings',
                  )}
                  onClick={() => {
                    feedbackTap()
                    onOpenSettings()
                  }}
                >
                  <Icon name="settings" size={20} />
                </MotionPress>
              )}
            </div>
          </>
        ) : (
          <>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              className="profile-subview-back"
              ariaLabel={t('profile.backToProfile')}
              onClick={() => {
                feedbackTap()
                goTab('profile')
              }}
            >
              <Icon name="chevron-left" size={18} />
              <span>
                {t('profile.backToProfile')}
              </span>
            </MotionPress>
            <h1 className="profile-page-title profile-page-title--sub">
              {subviewTitle}
            </h1>
            <div className="profile-header-actions profile-header-actions--sub">
              {onOpenSettings ? (
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="light"
                  className="icon-btn profile-settings-btn"
                  ariaLabel={t(
                    'profile.openSettings',
                  )}
                  onClick={() => {
                    feedbackTap()
                    onOpenSettings()
                  }}
                >
                  <Icon name="settings" size={20} />
                </MotionPress>
              ) : (
                <span
                  aria-hidden
                  className="profile-page-spacer"
                />
              )}
            </div>
          </>
        )}
      </header>

      <div className="profile-content">
        {isMainTab && (
          <>
            <ProfileHero
              avatarImageUrl={heroAvatarImage}
              shownName={shownName}
              username={username}
              editMode={editMode}
              displayName={displayName}
              saving={saving}
              palette={palette}
              onEditStart={handleEditStart}
              onSave={handleSave}
              onCancel={handleCancelEdit}
              onDisplayNameChange={setDisplayName}
              onAvatarFileSelected={
                handleAvatarFileChosen
              }
              onAvatarRejected={
                handleAvatarRejected
              }
              onShare={
                getInternalUserId()
                  ? () => setShareOpen(true)
                  : undefined
              }
            />
            <ProfileStats stats={stats} />
            <ListenerStats />
            <ArtistProfileCard />
            <ProfileActions
              onOpenImport={() => goTab('import')}
              onOpenComplaints={() => goTab('complaints')}
              onOpenDislikes={() => goTab('dislikes')}
              onOpenStats={() => goTab('stats')}
            />
            <ProfileUploadCallout />
            <ProfileTrackList
              tracks={myTracks}
              onPlay={playTrack}
              onToggleVisibility={
                handleToggleVisibility
              }
              onDelete={handleDelete}
              hasMore={myTracksHasMore}
              loadingMore={myTracksLoadingMore}
              onLoadMore={loadMoreMyTracks}
            />
          </>
        )}

        {!isMainTab && (
          <div
            key={tab}
            className="rp-subview"
            data-direction={navDirection}
          >
            {tab === 'import' && (
              <ImportView
                active={tab === 'import'}
                onImportComplete={refreshProfileData}
              />
            )}
            {tab === 'complaints' && <MyComplaintsList />}
            {tab === 'dislikes' && <DislikedView />}
            {tab === 'stats' && <ProfileStatsTab />}
          </div>
        )}
      </div>

      {shareOpen && getInternalUserId() && (
        <ProfileShareModal
          open={shareOpen}
          userId={getInternalUserId() as number}
          onClose={() => setShareOpen(false)}
        />
      )}
    </section>
  )
}
