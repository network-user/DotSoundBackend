import { useRef, useState } from 'react'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import { useExitTransition } from '@/hooks/useExitTransition'
import type { Track } from '@/types/api'

const BANDS = [
  '32', '64', '125', '250',
  '500', '1k', '4k', '16k',
]

const PRESETS: Record<string, number[]> = {
  Flat: [0, 0, 0, 0, 0, 0, 0, 0],
  'Bass Boost': [6, 5, 4, 2, 0, 0, 0, 0],
  'Treble Boost': [0, 0, 0, 0, 0, 2, 4, 6],
  Vocal: [-2, -1, 0, 3, 4, 3, 0, -1],
  Rock: [4, 3, 1, 0, -1, 1, 3, 4],
  Electronic: [5, 4, 1, 0, -2, 0, 3, 5],
  Acoustic: [3, 2, 0, 1, 2, 1, 2, 3],
  'Late Night': [4, 3, 2, 1, 0, 0, -1, -2],
}

const PRESET_NAMES = Object.keys(PRESETS)

export function Equalizer() {
  const {
    isEqOpen,
    closeEq,
    eqBands,
    eqPreset,
    eqBypassed,
    setEqBand,
    setEqPreset,
    toggleEqBypass,
    resetEq,
    track,
    isPlaying,
    playTrack,
  } = usePlayer()

  const [previewTracks, setPreviewTracks] =
    useState<Track[]>([])
  const [previewLoading, setPreviewLoading] =
    useState(false)
  const [previewError, setPreviewError] =
    useState<string | null>(null)
  const [previewSource, setPreviewSource] =
    useState<string | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)
  const confirmResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handlePreset = (name: string) => {
    const values = PRESETS[name]
    if (!values) return
    values.forEach((g, i) => setEqBand(i, g))
    setEqPreset(name)
  }

  const handleBandChange = (
    idx: number,
    gain: number,
  ) => {
    setEqBand(idx, gain)
    setEqPreset(null)
  }

  const loadPreviewTracks = async () => {
    setPreviewLoading(true)
    setPreviewError(null)
    try {
      const mine = await api.getMyTracks(1, 8)
      const ownTracks = mine.items.filter(
        (item) => item.is_active,
      )
      if (ownTracks.length > 0) {
        setPreviewTracks(ownTracks)
        setPreviewSource('Мои треки')
        return
      }

      const popular = await api.getTracks({
        size: 8,
      })
      setPreviewTracks(
        popular.items.filter(
          (item) => item.is_active,
        ),
      )
      setPreviewSource('Рекомендованные')
    } catch {
      setPreviewError(
        'Не удалось загрузить треки для проверки',
      )
    } finally {
      setPreviewLoading(false)
    }
  }

  const handlePreviewTrack = async (
    item: Track,
  ) => {
    await playTrack(item)
    setPreviewTracks([])
    setPreviewSource(null)
  }

  const exit = useExitTransition(isEqOpen)
  if (!exit.mounted) return null

  return (
    <div
      className={`eq-backdrop${exit.cls}`}
      onClick={(e) => {
        if (e.target === e.currentTarget)
          closeEq()
      }}
    >
      <div className={`eq-sheet${exit.cls}`}>
        <div className="eq-handle" />

        <div className="eq-header">
          <div className="eq-header-main">
            <span className="eq-title">
              Эквалайзер
            </span>
            <span className="eq-subtitle">
              {eqPreset || 'Custom'}
            </span>
          </div>
          <div className="eq-header-actions">
            <button
              className={`chip${eqBypassed ? ' active' : ''}`}
              onClick={toggleEqBypass}
            >
              {eqBypassed ? 'Без EQ' : 'С EQ'}
            </button>
            <button
              className={`icon-btn${confirmReset ? ' eq-reset-confirm' : ''}`}
              title={confirmReset ? 'Нажмите ещё раз для сброса' : 'Сбросить EQ'}
              onClick={() => {
                if (confirmReset) {
                  if (confirmResetTimerRef.current) clearTimeout(confirmResetTimerRef.current)
                  setConfirmReset(false)
                  resetEq()
                } else {
                  setConfirmReset(true)
                  confirmResetTimerRef.current = setTimeout(() => setConfirmReset(false), 2500)
                }
              }}
            >
              {confirmReset
                ? <span style={{ fontSize: 12, fontWeight: 600 }}>Сбросить?</span>
                : <Icon name="undo" size={18} />
              }
            </button>
          </div>
        </div>

        <div className="eq-preview-card">
          {track ? (
            <>
              <div className="eq-preview-info">
                <span className="eq-preview-label">
                  {isPlaying
                    ? 'Проверка на текущем треке'
                    : 'Текущий трек готов для проверки'}
                </span>
                <strong className="eq-preview-title">
                  {track.title}
                </strong>
                <span className="eq-preview-artist">
                  {track.artist || '—'}
                </span>
              </div>
              <button
                className="eq-preview-toggle"
                onClick={toggleEqBypass}
              >
                {eqBypassed
                  ? 'Включить EQ'
                  : 'Сравнить с оригиналом'}
              </button>
            </>
          ) : (
            <>
              <div className="eq-preview-info">
                <span className="eq-preview-label">
                  Ничего не играет
                </span>
                <strong className="eq-preview-title">
                  Запустите трек для проверки
                </strong>
                <span className="eq-preview-artist">
                  Сначала покажем ваши треки,
                  потом популярные
                </span>
              </div>
              <button
                className="eq-preview-toggle"
                onClick={loadPreviewTracks}
                disabled={previewLoading}
              >
                {previewLoading
                  ? 'Загружаем...'
                  : 'Запустить для проверки'}
              </button>
            </>
          )}
        </div>

        {previewTracks.length > 0 && (
          <div className="eq-track-picker">
            <div className="eq-track-picker-header">
              <span className="eq-track-picker-title">
                {previewSource}
              </span>
              <button
                className="icon-btn"
                onClick={() => {
                  setPreviewTracks([])
                  setPreviewSource(null)
                }}
              >
                <Icon name="x" size={16} />
              </button>
            </div>
            <div className="eq-track-picker-list">
              {previewTracks.map((item) => (
                <button
                  key={item.id}
                  className="eq-track-option"
                  onClick={() =>
                    handlePreviewTrack(item)
                  }
                >
                  <div className="eq-track-option-info">
                    <span className="eq-track-option-title">
                      {item.title}
                    </span>
                    <span className="eq-track-option-artist">
                      {item.artist || '—'}
                    </span>
                  </div>
                  <Icon
                    name="play"
                    size={14}
                  />
                </button>
              ))}
            </div>
          </div>
        )}

        {previewError && (
          <div className="eq-preview-error">
            {previewError}
          </div>
        )}

        <div className="eq-presets">
          {PRESET_NAMES.map((name) => (
            <button
              key={name}
              className={`chip${eqPreset === name ? ' active' : ''}`}
              onClick={() => handlePreset(name)}
            >
              {name}
            </button>
          ))}
          {eqPreset === null && (
            <span className="chip active">
              Custom
            </span>
          )}
        </div>

        <div className="eq-sliders">
          {BANDS.map((label, i) => (
            <div key={label} className="eq-band">
              <span className="eq-db">
                {eqBands[i] > 0 ? '+' : ''}
                {eqBands[i]}
              </span>
              <input
                type="range"
                className="eq-slider"
                min={-12}
                max={12}
                step={1}
                value={eqBands[i]}
                onChange={(e) =>
                  handleBandChange(
                    i,
                    Number(e.target.value),
                  )
                }
              />
              <span className="eq-label">
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
