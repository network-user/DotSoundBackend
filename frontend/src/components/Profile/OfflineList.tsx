import { useEffect, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import {
  clearAllOffline,
  getCachedTracks,
  getEffectiveCacheLimit,
  getStorageInfo,
  removeTrack,
  subscribeCacheChanges,
  type OfflineRecord,
} from '@/lib/offlineCache'

function fmtBytes(n: number): string {
  if (!n) return '0 МБ'
  const mb = n / (1024 * 1024)
  if (mb < 1024) return `${mb.toFixed(1)} МБ`
  return `${(mb / 1024).toFixed(2)} ГБ`
}

const WARN_THRESHOLD = 0.8
const FULL_THRESHOLD = 0.95

function fillTone(ratio: number): 'ok' | 'warn' | 'full' {
  if (ratio >= FULL_THRESHOLD) return 'full'
  if (ratio >= WARN_THRESHOLD) return 'warn'
  return 'ok'
}

function fillColor(tone: 'ok' | 'warn' | 'full'): string {
  if (tone === 'full') return 'var(--color-error, #e5484d)'
  if (tone === 'warn') return 'var(--color-warning, #f0a929)'
  return 'var(--color-accent, #3a86ff)'
}

export function OfflineList() {
  const [items, setItems] = useState<OfflineRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [storage, setStorage] = useState<{
    used: number
    quota: number
  }>({ used: 0, quota: 0 })
  const [effectiveLimit, setEffectiveLimit] = useState<number>(
    Number.POSITIVE_INFINITY,
  )

  const reload = async () => {
    const [list, info, limit] = await Promise.all([
      getCachedTracks(),
      getStorageInfo(),
      getEffectiveCacheLimit(),
    ])
    setItems(list)
    setStorage(info)
    setEffectiveLimit(limit)
    setLoading(false)
  }

  useEffect(() => {
    void reload()
    const unsub = subscribeCacheChanges(() => {
      void reload()
    })
    return unsub
  }, [])

  const onRemove = async (id: number) => {
    await removeTrack(id)
    setItems((prev) =>
      prev.filter((it) => it.trackId !== id),
    )
    showIsland({
      kind: 'toast',
      title: 'Трек удалён из скачанных',
      durationMs: 2200,
    })
  }

  const onClearAll = async () => {
    if (!items.length) return
    await clearAllOffline()
    await reload()
    showIsland({
      kind: 'toast',
      title: 'Скачанные треки очищены',
      durationMs: 2200,
    })
  }

  const totalBytes = items.reduce(
    (s, it) => s + it.bytes,
    0,
  )

  const hasLimit = Number.isFinite(effectiveLimit) && effectiveLimit > 0
  const ratio = hasLimit
    ? Math.min(1, totalBytes / effectiveLimit)
    : 0
  const tone = fillTone(ratio)

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
          ·{' '}
          {hasLimit
            ? `${fmtBytes(totalBytes)} / ${fmtBytes(effectiveLimit)}`
            : fmtBytes(totalBytes)}
          {!hasLimit && storage.quota > 0 && (
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
      {hasLimit && (
        <div
          className={`offline-list-meter offline-list-meter--${tone}`}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(ratio * 100)}
          style={{
            position: 'relative',
            height: 6,
            borderRadius: 999,
            background: 'var(--color-surface-2, rgba(127,127,127,0.18))',
            overflow: 'hidden',
            margin: '6px 0 4px',
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              bottom: 0,
              width: `${ratio * 100}%`,
              background: fillColor(tone),
              transition:
                'width 240ms ease-out, background 240ms ease',
            }}
          />
        </div>
      )}
      {hasLimit && tone === 'warn' && (
        <div
          className="offline-list-hint offline-list-hint--warn"
          style={{
            fontSize: 12,
            opacity: 0.85,
            marginBottom: 6,
          }}
        >
          Скоро закончится место. Старые треки будут
          вытесняться автоматически.
        </div>
      )}
      {hasLimit && tone === 'full' && (
        <div
          className="offline-list-hint offline-list-hint--full"
          style={{
            fontSize: 12,
            color: 'var(--color-error, #e5484d)',
            marginBottom: 6,
          }}
        >
          Лимит почти исчерпан. Удалите ненужные
          треки или увеличьте лимит в настройках.
        </div>
      )}
      <div className="track-list re-tl-root">
        {items
          .filter(
            (
              it,
            ): it is OfflineRecord & {
              track: NonNullable<OfflineRecord['track']>
            } => Boolean(it.track),
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
