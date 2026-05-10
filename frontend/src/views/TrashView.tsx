import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

const PAGE_SIZE = 50

export function TrashView() {
  const { t } = useTranslation()
  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.getMyTrash(1, PAGE_SIZE)
      setTracks(res.items as Track[])
    } catch {
      setTracks([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const restore = async (trackId: number) => {
    setBusyId(trackId)
    try {
      await api.restoreTrack(trackId)
      setTracks((prev) =>
        (prev ?? []).filter((t) => t.id !== trackId),
      )
    } catch {
      /* ignore */
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="trash-view">
      <header className="page-header">
        <h1>{t('trash.title', 'Удалённые треки')}</h1>
        <p className="settings-hint">
          {t(
            'trash.hint',
            'Треки можно восстановить в течение grace-периода, ' +
              'после чего они будут удалены безвозвратно.',
          )}
        </p>
      </header>
      {loading && tracks === null ? (
        <div className="page-loading">{t('common.loading', 'Загрузка…')}</div>
      ) : (tracks?.length ?? 0) === 0 ? (
        <div className="page-empty">
          {t('trash.empty', 'Корзина пуста.')}
        </div>
      ) : (
        <ul className="trash-list">
          {tracks!.map((track) => (
            <li key={track.id} className="trash-list__item">
              <div className="trash-list__meta">
                <div className="trash-list__title">
                  {track.title}
                </div>
                {track.artist ? (
                  <div className="trash-list__artist">
                    {track.artist}
                  </div>
                ) : null}
              </div>
              <MotionPress
                type="button"
                variant="primary"
                haptic="medium"
                className="btn-primary"
                disabled={busyId === track.id}
                onClick={() => void restore(track.id)}
              >
                {busyId === track.id
                  ? '…'
                  : t('trash.restore', 'Восстановить')}
              </MotionPress>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
