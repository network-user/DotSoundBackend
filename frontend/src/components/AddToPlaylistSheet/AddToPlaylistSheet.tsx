import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { Sheet } from '@/components/ui/Sheet'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import { showIsland } from '@/lib/island'
import { useSound } from '@/store/SoundContext'
import type { Playlist } from '@/types/api'

type Props = {
  open: boolean
  onClose: () => void
  trackId: number
}

export function AddToPlaylistSheet({
  open,
  onClose,
  trackId,
}: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const sound = useSound()
  const [playlists, setPlaylists] = useState<Playlist[] | null>(
    null,
  )
  const [busyId, setBusyId] = useState<number | null>(null)

  useEffect(() => {
    if (!open) {
      setPlaylists(null)
      return
    }
    let cancelled = false
    api
      .getPlaylists({ page: 1, size: 100 })
      .then((list) => {
        if (!cancelled) setPlaylists(list)
      })
      .catch(() => {
        if (!cancelled) setPlaylists([])
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const pick = async (pl: Playlist) => {
    if (busyId !== null) return
    setBusyId(pl.id)
    try {
      await api.addTrackToPlaylist(pl.id, trackId)
      sound.play('notificationInfo')
      showIsland({
        kind: 'toast',
        title: t('redesign.library.playlistTrackAddedToast', {
          playlist: pl.name,
        }),
        durationMs: 2400,
      })
      onClose()
    } catch {
      sound.play('notificationError')
      showIsland({
        kind: 'error',
        title: t('redesign.library.playlistTrackAddFail'),
        durationMs: 4500,
      })
    } finally {
      setBusyId(null)
    }
  }

  const goPlaylistsTab = () => {
    onClose()
    navigate('/library?tab=playlists')
  }

  const loading = open && playlists === null

  return (
    <Sheet
      open={open}
      onClose={onClose}
      ariaLabel={t(
        'redesign.library.addToPlaylistSheetTitle',
      )}
    >
      <div className="rd-pl-playlist-pick-sheet">
        <h2 className="rd-pl-playlist-pick-title">
          {t('redesign.library.addToPlaylistSheetTitle')}
        </h2>

        {loading ? (
          <p className="rd-pl-playlist-pick-loading">
            {t('redesign.library.addToPlaylistSheetLoading')}
          </p>
        ) : playlists && playlists.length === 0 ? (
          <div className="rd-pl-playlist-pick-empty">
            <p>{t('redesign.library.addToPlaylistSheetEmpty')}</p>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary"
              style={{ marginTop: 12 }}
              onClick={() => goPlaylistsTab()}
            >
              {t('redesign.library.addToPlaylistSheetGoPlaylists')}
            </MotionPress>
          </div>
        ) : (
          <div
            className="rd-pl-playlist-pick-scroll"
            role="list"
          >
            {playlists?.map((pl) => {
              const busy = busyId === pl.id
              const meta = busy
                ? t('redesign.library.addToPlaylistSheetAdding')
                : pl.track_count != null
                  ? t('redesign.library.playlistTracksCount', {
                      count: pl.track_count,
                    })
                  : null
              return (
                <button
                  key={pl.id}
                  type="button"
                  role="listitem"
                  className="rd-pl-playlist-pick-row"
                  disabled={busy}
                  aria-busy={busy}
                  onClick={() => void pick(pl)}
                >
                  <span>
                    <div className="rd-pl-playlist-pick-row-name">
                      {pl.name}
                    </div>
                    {meta ? (
                      <div className="rd-pl-playlist-pick-row-meta">
                        {meta}
                      </div>
                    ) : null}
                  </span>
                  {busy ? null : (
                    <Icon name="chevron-right" size={18} />
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </Sheet>
  )
}
