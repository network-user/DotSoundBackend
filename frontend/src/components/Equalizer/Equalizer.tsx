import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import { getInternalUserId } from '@/lib/telegram'

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
    setEqBand,
  } = usePlayer()

  const [activePreset, setActivePreset] =
    useState<string | null>('Flat')
  const [saveTimer, setSaveTimer] =
    useState<ReturnType<typeof setTimeout> | null>(
      null,
    )

  useEffect(() => {
    if (!isEqOpen) return
    const uid = getInternalUserId()
    if (!uid) return
    api
      .getEqSettings()
      .then((data) => {
        if (data?.bands?.length === 8) {
          data.bands.forEach(
            (g: number, i: number) =>
              setEqBand(i, g),
          )
          setActivePreset(data.preset || null)
        }
      })
      .catch(() => {})
  }, [isEqOpen])

  const debouncedSave = useCallback(
    (preset: string | null, bands: number[]) => {
      if (saveTimer) clearTimeout(saveTimer)
      const t = setTimeout(() => {
        api
          .saveEqSettings({ preset, bands })
          .catch(() => {})
      }, 1000)
      setSaveTimer(t)
    },
    [saveTimer],
  )

  const handlePreset = (name: string) => {
    const values = PRESETS[name]
    if (!values) return
    values.forEach((g, i) => setEqBand(i, g))
    setActivePreset(name)
    debouncedSave(name, values)
  }

  const handleBandChange = (
    idx: number,
    gain: number,
  ) => {
    setEqBand(idx, gain)
    setActivePreset(null)
    const bands = [...eqBands]
    bands[idx] = gain
    debouncedSave(null, bands)
  }

  const handleReset = () => handlePreset('Flat')

  if (!isEqOpen) return null

  return (
    <div
      className="eq-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget)
          closeEq()
      }}
    >
      <div className="eq-sheet">
        <div className="eq-handle" />

        <div className="eq-header">
          <span className="eq-title">
            Эквалайзер
          </span>
          <button
            className="icon-btn"
            onClick={handleReset}
          >
            ↺
          </button>
        </div>

        <div className="eq-presets">
          {PRESET_NAMES.map((name) => (
            <button
              key={name}
              className={`chip${activePreset === name ? ' active' : ''}`}
              onClick={() => handlePreset(name)}
            >
              {name}
            </button>
          ))}
          {activePreset === null && (
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
