import { useEffect, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { useToast } from '@/components/ui/Toast'
import {
  clearAllOffline,
  getCachedTracks,
  getStorageInfo,
  removeTrack,
  type OfflineRecord,
} from '@/lib/offlineCache'
import { usePlayerActions } from '@/store/PlayerContext'

function fmtBytes(n: number): string {
  if (!n) return '0 МБ'
  const mb = n / (1024 * 1024)
  if (mb < 1024) return `${mb.toFixed(1)} МБ`
  return `${(mb / 1024).toFixed(2)} ГБ`
}

export function OfflineList() {
  const [items, setItems] = useState<OfflineRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [storage, setStorage] = useState<{
    used: number
    quota: number
  }>({ used: 0, quota: 0 })
  const { playTrack } = usePlayerActions()
  const toast = useToast()

  const reload = async () => {
    setLoading(true)
    const list = await getCachedTracks()
    setItems(list)
    setStorage(await getStorageInfo())
    setLoading(false)
  }

  useEffect(() => {
    reload()
  }, [])

  const onRemove = async (id: number) => {
    await removeTrack(id)
    setItems((prev) =>
      prev.filter((it) => it.trackId !== id),
    )
    toast.info('Трек удалён из скачанных')
  }

  const onClearAll = async () => {
    if (!items.length) return
    await clearAllOffline()
    await reload()
    toast.info('Скачанные треки очищены')
  }

  const totalBytes = items.reduce(
    (s, it) => s + it.bytes,
    0,
  )

  if (loading) {
    return (
      <div className="offline-list-loading">
        Загрузка…
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="offline-list-empty">
        <Icon
          name="cloud-download"
          size={32}
          className="offline-list-empty-icon"
        />
        <div className="offline-list-empty-title">
          Здесь будут скачанные треки
        </div>
        <div className="offline-list-empty-hint">
          Откройте трек и нажмите «Скачать» — он
          будет доступен без интернета.
        </div>
      </div>
    )
  }

  return (
    <div className="offline-list">
      <div className="offline-list-header">
        <div>
          <strong>
            {items.length} трек{items.length === 1 ? '' : 'а'}
          </strong>{' '}
          · {fmtBytes(totalBytes)}
          {storage.quota > 0 && (
            <>
              {' / '}
              {fmtBytes(storage.quota)} доступно
            </>
          )}
        </div>
        <button
          className="queue-action-btn"
          onClick={onClearAll}
        >
          Очистить всё
        </button>
      </div>
      <div className="offline-list-rows">
        {items.map((it) => (
          <div
            key={it.trackId}
            className="offline-list-row"
          >
            <button
              className="offline-list-main"
              onClick={() => playTrack(it.track)}
            >
              <div className="offline-list-cover">
                {it.track.cover_key ? (
                  <img
                    src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(it.track.cover_key)}`}
                    alt=""
                  />
                ) : (
                  <Icon name="music" size={18} />
                )}
              </div>
              <div className="offline-list-meta">
                <div className="offline-list-title">
                  {it.track.title}
                </div>
                <div className="offline-list-sub">
                  {it.track.artist || '—'} ·{' '}
                  {fmtBytes(it.bytes)}
                </div>
              </div>
            </button>
            <button
              className="icon-btn offline-list-remove"
              onClick={() => onRemove(it.trackId)}
              aria-label="Удалить"
            >
              <Icon name="trash" size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
