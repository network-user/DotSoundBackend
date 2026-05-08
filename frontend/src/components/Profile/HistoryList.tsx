import { useCallback, useEffect, useMemo, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { api } from '@/lib/api'
import { usePlayerMeta } from '@/store/PlayerContext'
import type { Track } from '@/types/api'

function mergeSessionAndApi(
  current: Track | null,
  sessionHistory: Track[],
  apiItems: Track[],
): Track[] {
  const out: Track[] = []
  const seen = new Set<number>()

  if (current) {
    out.push(current)
    seen.add(current.id)
  }
  for (const t of [...sessionHistory].reverse()) {
    if (seen.has(t.id)) continue
    out.push(t)
    seen.add(t.id)
  }
  for (const t of apiItems) {
    if (seen.has(t.id)) continue
    out.push(t)
    seen.add(t.id)
  }
  return out
}

export function HistoryList() {
  const { track, history: sessionHistory } =
    usePlayerMeta()
  const [apiTracks, setApiTracks] = useState<
    Track[] | null
  >(null)
  const [loadError, setLoadError] = useState(false)

  const load = useCallback(() => {
    setLoadError(false)
    api
      .getListenHistory(80)
      .then((res) => setApiTracks(res.items))
      .catch(() => {
        setLoadError(true)
        setApiTracks([])
      })
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const listenMetaById = useMemo(() => {
    const m = new Map<
      number,
      { at: string; sec: number }
    >()
    if (!apiTracks) return m
    for (const row of apiTracks) {
      if (!row.last_listen_at) continue
      m.set(row.id, {
        at: row.last_listen_at,
        sec: row.last_listen_seconds ?? 0,
      })
    }
    return m
  }, [apiTracks])

  const rows = useMemo(() => {
    if (apiTracks === null) return null
    const merged = mergeSessionAndApi(
      track,
      sessionHistory,
      apiTracks,
    )
    return merged.map((row) => {
      const lm = listenMetaById.get(row.id)
      if (!lm) return row
      return {
        ...row,
        last_listen_at: lm.at,
        last_listen_seconds: lm.sec,
      }
    })
  }, [apiTracks, listenMetaById, sessionHistory, track])

  if (rows === null) {
    return (
      <div className="offline-list">
        <div className="loader" style={{ margin: 24 }} />
      </div>
    )
  }

  if (rows.length === 0) {
    return (
      <div className="my-complaints-empty">
        <Icon
          name="clock"
          size={28}
          className="offline-list-empty-icon"
        />
        <div className="offline-list-empty-title">
          {loadError
            ? 'Не удалось загрузить историю'
            : 'Пока нет прослушиваний'}
        </div>
        <div className="offline-list-empty-hint">
          {loadError
            ? 'Проверь соединение и обнови раздел.'
            : 'Включи треки — история строится из твоих прослушиваний в аккаунте. Текущий плейлист в плеере тоже отображается выше, когда играет музыка.'}
        </div>
        {loadError && (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="empty-cta re-history-retry"
            onClick={load}
          >
            Повторить
          </MotionPress>
        )}
      </div>
    )
  }

  return (
    <div className="offline-list">
      <div className="offline-list-header">
        <div>
          <strong>{rows.length}</strong> в истории
        </div>
      </div>
      <div className="track-list re-tl-root re-history-as-tracklist">
        {rows.map((tr, i) => (
          <div
            key={`h-${tr.id}-${i}`}
            className="track-list-item re-tl-item"
          >
            <TrackCard track={tr} />
          </div>
        ))}
      </div>
    </div>
  )
}
