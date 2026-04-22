import { Icon } from '@/components/Icon/Icon'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import type { Track } from '@/types/api'

export function HistoryList() {
  const { history } = usePlayerMeta()
  const { playTrack } = usePlayerActions()

  if (history.length === 0) {
    return (
      <div className="my-complaints-empty">
        <Icon
          name="clock"
          size={28}
          className="offline-list-empty-icon"
        />
        <div className="offline-list-empty-title">
          История пуста
        </div>
        <div className="offline-list-empty-hint">
          Тут появятся треки, которые ты слушал в
          этой сессии.
        </div>
      </div>
    )
  }

  return (
    <div className="offline-list">
      <div className="offline-list-header">
        <div>
          <strong>{history.length}</strong> в
          истории
        </div>
      </div>
      <div className="offline-list-rows">
        {[...history].reverse().map((t: Track, i) => (
          <div
            key={`h-${t.id}-${i}`}
            className="offline-list-row"
          >
            <button
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
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
