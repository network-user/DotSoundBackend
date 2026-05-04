import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import type { Track } from '@/types/api'

export function RadioView() {
  const navigate = useNavigate()
  const { track: currentTrack } = usePlayerMeta()
  const {
    startRadio,
    stopRadio,
    radioMode,
  } = usePlayerActions()

  const [historyTracks, setHistoryTracks] = useState<Track[]>([])
  const historyRef = useRef<Track[]>([])

  useEffect(() => {
    if (!currentTrack) return
    if (!radioMode) return
    if (
      historyRef.current.length > 0 &&
      historyRef.current[historyRef.current.length - 1].id ===
        currentTrack.id
    )
      return
    historyRef.current = [
      ...historyRef.current,
      currentTrack,
    ].slice(-30)
    setHistoryTracks([...historyRef.current].reverse())
  }, [currentTrack, radioMode])

  const handleStartRadio = async () => {
    if (!currentTrack) return
    historyRef.current = []
    setHistoryTracks([])
    await startRadio(currentTrack)
  }

  const handleStop = () => {
    stopRadio()
  }

  return (
    <section className="view active">
      <div className="view-header">
        <button
          className="icon-btn"
          onClick={() => navigate(-1)}
          aria-label="Назад"
        >
          <Icon
            name="chevron"
            size={20}
            className="back-chevron"
          />
        </button>
        <div style={{ flex: 1 }}>
          <h2>Радио</h2>
          <span className="hint">
            {radioMode
              ? 'Бесконечное радио включено'
              : 'Бесконечная подборка похожих треков'}
          </span>
        </div>
        {radioMode && (
          <button
            className="icon-btn"
            onClick={handleStop}
            aria-label="Остановить радио"
            title="Остановить радио"
          >
            <Icon name="x" size={20} />
          </button>
        )}
      </div>

      <div style={{ padding: '16px' }}>
        {!radioMode ? (
          <button
            className="btn-primary"
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
            }}
            onClick={handleStartRadio}
            disabled={!currentTrack}
          >
            <Icon name="radio" size={18} />
            {currentTrack
              ? 'Запустить бесконечное радио'
              : 'Сначала выберите трек'}
          </button>
        ) : (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 14px',
              borderRadius: 'var(--r-lg)',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
            }}
          >
            <span className="player-radio-badge player-radio-badge--active">
              <span className="player-radio-badge__dot" />
              Радио
            </span>
            <span
              style={{
                flex: 1,
                fontSize: 13,
                color: 'var(--text-secondary)',
              }}
            >
              {currentTrack?.title ?? '—'}
            </span>
            <button
              className="icon-btn"
              onClick={handleStop}
              aria-label="Стоп"
              style={{ flexShrink: 0 }}
            >
              <Icon name="x" size={16} />
            </button>
          </div>
        )}
      </div>

      {historyTracks.length > 0 && (
        <>
          <div className="home-section-header" style={{ paddingTop: 12 }}>
            <span className="home-section-header__title">
              История прослушивания
            </span>
          </div>
          <TrackList tracks={historyTracks} emptyMessage="" />
        </>
      )}

      {!radioMode && !currentTrack && (
        <p
          style={{
            padding: '24px 16px',
            textAlign: 'center',
            color: 'var(--text-secondary)',
            fontSize: 14,
          }}
        >
          Выберите трек на главной или в поиске, а затем запустите
          радио
        </p>
      )}
    </section>
  )
}
