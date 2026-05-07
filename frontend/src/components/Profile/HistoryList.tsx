import { useCallback, useEffect, useMemo, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
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
  const { playTrack } = usePlayerActions()
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

  const rows = useMemo(() => {
    if (apiTracks === null) return null
    return mergeSessionAndApi(
      track,
      sessionHistory,
      apiTracks,
    )
  }, [apiTracks, sessionHistory, track])

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
      <div className="offline-list-rows">
        {rows.map((t, i) => (
          <div
            key={`h-${t.id}-${i}`}
            className="offline-list-row"
          >
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="offline-list-main"
              onClick={() => playTrack(t)}
            >
              <div className="offline-list-cover">
                {t.cover_key ? (
                  <img
                    src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(t.cover_key)}`}
                    alt=""
                  />
                ) : (
                  <Icon name="music" size={18} />
                )}
              </div>
              <div className="offline-list-meta">
                <div className="offline-list-title">
                  {t.title}
                </div>
                <div className="offline-list-sub">
                  {t.artist || '—'}
                </div>
              </div>
            </MotionPress>
          </div>
        ))}
      </div>
    </div>
  )
}
