import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import type { Track } from '@/types/api'

function formatHistoryWhen(iso: string): string {
  const d = new Date(iso)
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

function formatListened(sec: number): string {
  if (!sec || sec < 1) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

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
  const { t } = useTranslation()
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
      <div className="offline-list-rows">
        {rows.map((tr, i) => (
          <div
            key={`h-${tr.id}-${i}`}
            className="offline-list-row"
          >
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="offline-list-main"
              onClick={() => playTrack(tr)}
            >
              <div className="offline-list-cover">
                {tr.cover_key ? (
                  <img
                    src={`/api/v1/tracks/cover_proxy?key=${encodeURIComponent(tr.cover_key)}`}
                    alt=""
                  />
                ) : (
                  <Icon name="music" size={18} />
                )}
              </div>
              <div className="offline-list-meta">
                <div className="offline-list-title">
                  {tr.title}
                </div>
                <div className="offline-list-sub">
                  {tr.artist || '—'}
                </div>
                {tr.last_listen_at && (
                  <div className="offline-list-hint">
                    {formatListened(tr.last_listen_seconds ?? 0)
                      ? t(
                          'redesign.library.historyWhenAndDur',
                          {
                            when: formatHistoryWhen(
                              tr.last_listen_at,
                            ),
                            duration: formatListened(
                              tr.last_listen_seconds ??
                                0,
                            ),
                          },
                        )
                      : t(
                          'redesign.library.historyWhenOnly',
                          {
                            when: formatHistoryWhen(
                              tr.last_listen_at,
                            ),
                          },
                        )}
                  </div>
                )}
              </div>
            </MotionPress>
          </div>
        ))}
      </div>
    </div>
  )
}
