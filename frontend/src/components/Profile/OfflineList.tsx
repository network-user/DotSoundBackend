import { useEffect, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import {
  clearAllOffline,
  getCachedTracks,
  getStorageInfo,
  removeTrack,
  type OfflineRecord,
} from '@/lib/offlineCache'

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
    showIsland({ kind: 'toast', title: 'Трек удалён из скачанных', durationMs: 2200 })
  }

  const onClearAll = async () => {
    if (!items.length) return
    await clearAllOffline()
    await reload()
    showIsland({ kind: 'toast', title: 'Скачанные треки очищены', durationMs: 2200 })
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
        <MotionPress
          type="button"
          variant="ghost"
          haptic="light"
          className="queue-action-btn"
          onClick={onClearAll}
        >
          Очистить всё
        </MotionPress>
      </div>
      <div className="track-list re-tl-root">
        {items
          .filter(
            (it): it is OfflineRecord & { track: NonNullable<OfflineRecord['track']> } =>
              Boolean(it.track),
          )
          .map((it) => (
          <div
            key={it.trackId}
            className="offline-list-row offline-list-row--card"
          >
            <div className="offline-list-row-card">
              <TrackCard
                track={it.track}
                summarySuffix={fmtBytes(it.bytes)}
              />
            </div>
            <MotionPress
              type="button"
              variant="icon"
              haptic="light"
              className="icon-btn offline-list-remove"
              ariaLabel="Удалить"
              onClick={() => onRemove(it.trackId)}
            >
              <Icon name="trash" size={16} />
            </MotionPress>
          </div>
        ))}
      </div>
    </div>
  )
}
