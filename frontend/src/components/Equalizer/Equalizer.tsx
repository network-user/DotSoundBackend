import { useEffect, useRef, useState } from 'react'
import { type PanInfo } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerPlayback,
} from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { useExitTransition } from '@/hooks/useExitTransition'
import { hapticTick, haptic } from '@/lib/telegram'
import type { Track } from '@/types/api'
import {
  m,
  SPRING_GENTLE,
  useReducedMotion,
} from '@/lib/motion'

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
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const { isPlaying } = usePlayerPlayback()
  const {
    isEqOpen,
    track,
    eqBands,
    eqPreset,
    eqBypassed,
  } = usePlayerMeta()
  const {
    closeEq,
    setEqBand,
    setEqPreset,
    toggleEqBypass,
    resetEq,
    playTrack,
  } = usePlayerActions()

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
    hapticTick()
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
        setPreviewSource(
          t('equalizer.sourceMine', 'Мои треки'),
        )
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
      setPreviewSource(
        t(
          'equalizer.sourceRecommended',
          'Рекомендованные',
        ),
      )
    } catch {
      setPreviewError(
        t(
          'equalizer.previewError',
          'Не удалось загрузить треки для проверки',
        ),
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

  useEffect(() => {
    if (!isEqOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeEq()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isEqOpen, closeEq])

  if (!exit.mounted) return null

  const handleDragEnd = (
    _: unknown,
    info: PanInfo,
  ) => {
    if (info.offset.y > 100) {
      haptic('light')
      closeEq()
    }
  }

  return (
    <div
      className={`eq-backdrop${exit.cls}`}
      onClick={(e) => {
        if (e.target === e.currentTarget)
          closeEq()
      }}
    >
      <m.div
        className={`eq-sheet rp-eq-sheet${exit.cls}`}
        drag={reduceMotion ? false : 'y'}
        dragConstraints={{ top: 0, bottom: 240 }}
        dragElastic={0.18}
        dragMomentum={false}
        onDragEnd={handleDragEnd}
        transition={SPRING_GENTLE}
      >
        <div className="eq-handle rp-eq__handle" />

        <div className="eq-header">
          <div className="eq-header-main">
            <span className="eq-title">
              {t('equalizer.title', 'Эквалайзер')}
            </span>
            <span className="eq-subtitle">
              {eqPreset ||
                t('equalizer.custom', 'Custom')}
            </span>
          </div>
          <div className="eq-header-actions">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              className={`chip${eqBypassed ? ' active' : ''}`}
              onClick={toggleEqBypass}
            >
              {eqBypassed
                ? t('equalizer.eqOff', 'Без EQ')
                : t('equalizer.eqOn', 'С EQ')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="icon"
              haptic="medium"
              className={`icon-btn${confirmReset ? ' eq-reset-confirm' : ''}`}
              title={
                confirmReset
                  ? t(
                      'equalizer.resetConfirm',
                      'Нажмите ещё раз для сброса',
                    )
                  : t(
                      'equalizer.resetTitle',
                      'Сбросить EQ',
                    )
              }
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
              {confirmReset ? (
                <span className="eq-reset-confirm-label">
                  {t(
                    'equalizer.resetAsk',
                    'Сбросить?',
                  )}
                </span>
              ) : (
                <Icon name="undo" size={18} />
              )}
            </MotionPress>
            <MotionPress
              type="button"
              variant="icon"
              haptic="light"
              className="icon-btn"
              ariaLabel={t('common.close', 'Закрыть')}
              onClick={closeEq}
            >
              <Icon name="x" size={18} />
            </MotionPress>
          </div>
        </div>

        <div className="eq-preview-card">
          {track ? (
            <>
              <div className="eq-preview-info">
                <span className="eq-preview-label">
                  {isPlaying
                    ? t(
                        'equalizer.previewCurrentPlaying',
                        'Проверка на текущем треке',
                      )
                    : t(
                        'equalizer.previewCurrentReady',
                        'Текущий трек готов для проверки',
                      )}
                </span>
                <strong className="eq-preview-title">
                  {track.title}
                </strong>
                <span className="eq-preview-artist">
                  {track.artist || '—'}
                </span>
              </div>
              <MotionPress
                type="button"
                variant="ghost"
                haptic="selection"
                className="eq-preview-toggle"
                onClick={toggleEqBypass}
              >
                {eqBypassed
                  ? t(
                      'equalizer.enableEq',
                      'Включить EQ',
                    )
                  : t(
                      'equalizer.compareOriginal',
                      'Сравнить с оригиналом',
                    )}
              </MotionPress>
            </>
          ) : (
            <>
              <div className="eq-preview-info">
                <span className="eq-preview-label">
                  {t(
                    'equalizer.nothingPlaying',
                    'Ничего не играет',
                  )}
                </span>
                <strong className="eq-preview-title">
                  {t(
                    'equalizer.startTrackForPreview',
                    'Запустите трек для проверки',
                  )}
                </strong>
                <span className="eq-preview-artist">
                  {t(
                    'equalizer.previewSourceHint',
                    'Сначала покажем ваши треки, потом популярные',
                  )}
                </span>
              </div>
              <MotionPress
                type="button"
                variant="primary"
                haptic="medium"
                className="eq-preview-toggle"
                onClick={loadPreviewTracks}
                disabled={previewLoading}
              >
                {previewLoading
                  ? t(
                      'equalizer.loading',
                      'Загружаем...',
                    )
                  : t(
                      'equalizer.startPreview',
                      'Запустить для проверки',
                    )}
              </MotionPress>
            </>
          )}
        </div>

        {previewTracks.length > 0 && (
          <div className="eq-track-picker">
            <div className="eq-track-picker-header">
              <span className="eq-track-picker-title">
                {previewSource}
              </span>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t(
                  'common.close',
                  'Закрыть',
                )}
                onClick={() => {
                  setPreviewTracks([])
                  setPreviewSource(null)
                }}
              >
                <Icon name="x" size={16} />
              </MotionPress>
            </div>
            <div className="eq-track-picker-list">
              {previewTracks.map((item) => (
                <MotionPress
                  key={item.id}
                  type="button"
                  variant="ghost"
                  haptic="light"
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
                  <MorphIcon
                    name="play"
                    size={14}
                    filled
                  />
                </MotionPress>
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
            <MotionPress
              key={name}
              type="button"
              variant="ghost"
              haptic="selection"
              className={`chip${eqPreset === name ? ' active' : ''}`}
              onClick={() => handlePreset(name)}
            >
              {name}
            </MotionPress>
          ))}
          {eqPreset === null && (
            <span className="chip active">
              {t('equalizer.custom', 'Custom')}
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
      </m.div>
    </div>
  )
}
