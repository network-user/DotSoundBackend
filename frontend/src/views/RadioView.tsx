import {
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { Waveform } from '@/components/Waveform/Waveform'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { AudioRipple } from '@/components/ui/AudioRipple'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { api } from '@/lib/api'
import { extractCoverPalette } from '@/lib/coverPalette'
import { getPrefetchManager } from '@/lib/prefetch/PrefetchManager'
import { haptic } from '@/lib/telegram'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerPlayback,
} from '@/store/PlayerContext'
import {
  m,
  SPRING_GENTLE,
  SPRING_SNAPPY,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import type { Track } from '@/types/api'

function coverUrl(key: string | null): string | null {
  if (!key) return null
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

const SWIPE_DISTANCE_THRESHOLD_PX = 56
const SWIPE_VELOCITY_THRESHOLD = 0.55 // px per ms
const DRAG_MAX_OFFSET_PX = 140
const TAP_MAX_OFFSET_PX = 6
const PEEK_DISTANCE_PX = 64
const RUBBER_BAND = 0.55

function rubberBand(value: number, max: number): number {
  if (Math.abs(value) <= max) return value
  const sign = value < 0 ? -1 : 1
  const over = Math.abs(value) - max
  return sign * (max + Math.pow(over, RUBBER_BAND) * 8)
}

export function RadioView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { track: currentTrack, queue, radioSessionTimeline } =
    usePlayerMeta()
  const { isPlaying } = usePlayerPlayback()
  const {
    playNext,
    playPrev,
    playRadioPrevious,
    playTrack,
    togglePlay,
    startRadio,
    stopRadio,
    radioMode,
    getAnalyser,
  } = usePlayerActions()

  const [slideDirection, setSlideDirection] = useState(1)
  const [isSwitching, setIsSwitching] = useState(false)
  const [dragX, setDragX] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [radioPreviewTracks, setRadioPreviewTracks] = useState<Track[]>([])
  const [accentColor, setAccentColor] = useState<string | undefined>(undefined)

  const switchingRef = useRef(false)
  const pointerRef = useRef<{
    pointerId: number
    startX: number
    startY: number
    lastX: number
    lastT: number
    velocity: number
    offsetX: number
    offsetY: number
  } | null>(null)
  const reduceMotion = useReducedMotion()

  const historyTracks = useMemo(
    () => [...radioSessionTimeline].reverse(),
    [radioSessionTimeline],
  )

  const heroCover = currentTrack ? coverUrl(currentTrack.cover_key) : null
  const isLive = Boolean(currentTrack && isPlaying)

  const nextTrack = queue[0] ?? radioPreviewTracks[0] ?? null
  const nextCover = nextTrack ? coverUrl(nextTrack.cover_key) : null
  const prevTrack =
    radioSessionTimeline.length > 1
      ? radioSessionTimeline[radioSessionTimeline.length - 2] ?? null
      : null
  const prevCover = prevTrack ? coverUrl(prevTrack.cover_key) : null

  useEffect(() => {
    if (!heroCover) {
      setAccentColor(undefined)
      return
    }
    let cancelled = false
    void extractCoverPalette(heroCover).then((palette) => {
      if (!cancelled) setAccentColor(palette?.tones[0])
    })
    return () => {
      cancelled = true
    }
  }, [heroCover])

  useEffect(() => {
    if (!radioMode || !currentTrack) {
      setRadioPreviewTracks([])
      return
    }
    if (queue.length > 0) {
      setRadioPreviewTracks([])
      return
    }
    let cancelled = false
    const excludeIds = [
      currentTrack.id,
      ...radioSessionTimeline.map((track) => track.id),
      ...queue.map((track) => track.id),
    ]
    api
      .getRadio(currentTrack.id, 14, excludeIds)
      .then((res) => {
        if (cancelled) return
        const candidates = res.tracks.filter(
          (track) =>
            track.id !== currentTrack.id &&
            !queue.some((q) => q.id === track.id),
        )
        setRadioPreviewTracks(candidates)
        if (!candidates.length) return
        void getPrefetchManager().enqueue(candidates, {
          context: 'radio',
          replaceContext: true,
        })
      })
      .catch(() => {
        if (cancelled) return
        setRadioPreviewTracks([])
      })
    return () => {
      cancelled = true
    }
  }, [radioMode, currentTrack?.id, queue, radioSessionTimeline])

  const handleStartRadio = async () => {
    if (!currentTrack) return
    haptic('medium')
    await startRadio(currentTrack)
  }

  const handleStop = () => {
    haptic('light')
    stopRadio()
  }

  const handleSwipe = async (direction: 'next' | 'previous') => {
    if (switchingRef.current) return
    switchingRef.current = true
    setIsSwitching(true)
    setSlideDirection(direction === 'next' ? 1 : -1)
    haptic('light')
    try {
      if (direction === 'next') {
        const ok = await playNext()
        if (!ok) {
          showIsland({
            kind: 'toast',
            title: t('redesign.home.radioNextUnavailable'),
            durationMs: 2200,
          })
        }
        return
      }
      if (radioMode) {
        const ok = await playRadioPrevious()
        if (!ok) {
          showIsland({
            kind: 'toast',
            title: t('redesign.home.radioPrevUnavailable'),
            durationMs: 2200,
          })
        }
        return
      }
      await playPrev()
    } finally {
      switchingRef.current = false
      setIsSwitching(false)
    }
  }

  const handlePointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!currentTrack || switchingRef.current) return
    pointerRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      lastX: e.clientX,
      lastT: performance.now(),
      velocity: 0,
      offsetX: 0,
      offsetY: 0,
    }
    setIsDragging(true)
    setDragX(0)
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const handlePointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const p = pointerRef.current
    if (!p || p.pointerId !== e.pointerId) return
    const rawOffset = e.clientX - p.startX
    const offset = rubberBand(rawOffset, DRAG_MAX_OFFSET_PX)
    const now = performance.now()
    const dt = Math.max(1, now - p.lastT)
    p.velocity = (e.clientX - p.lastX) / dt
    p.lastX = e.clientX
    p.lastT = now
    p.offsetX = offset
    p.offsetY = e.clientY - p.startY
    setDragX(offset)
    if (Math.abs(offset) > 4) e.preventDefault()
  }

  const handlePointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    const p = pointerRef.current
    if (!p || p.pointerId !== e.pointerId) return
    pointerRef.current = null
    setIsDragging(false)
    setDragX(0)
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }

    const isTap =
      Math.abs(p.offsetX) <= TAP_MAX_OFFSET_PX &&
      Math.abs(p.offsetY) <= TAP_MAX_OFFSET_PX

    if (isTap && currentTrack && !switchingRef.current) {
      haptic('light')
      void togglePlay()
      return
    }

    const fastSwipe = Math.abs(p.velocity) >= SWIPE_VELOCITY_THRESHOLD
    const farSwipe = Math.abs(p.offsetX) >= SWIPE_DISTANCE_THRESHOLD_PX

    if (!fastSwipe && !farSwipe) return

    const goingLeft = p.offsetX < 0 || (fastSwipe && p.velocity < 0)
    void handleSwipe(goingLeft ? 'next' : 'previous')
  }

  const dragRatio = Math.max(
    -1,
    Math.min(1, dragX / DRAG_MAX_OFFSET_PX),
  )

  return (
    <section className="view active rh-radio-root">
      <div className="view-header">
        <button
          type="button"
          className="icon-btn"
          onClick={() => navigate(-1)}
          aria-label={t('redesign.home.back')}
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div className="rh-radio-header__meta">
          <h2>{t('redesign.home.radioTitle')}</h2>
          <span className="hint">
            {radioMode
              ? t('redesign.home.radioSubtitleOn')
              : t('redesign.home.radioSubtitleIdle')}
          </span>
        </div>
        {radioMode ? (
          <button
            type="button"
            className="rh-radio-live-chip"
            onClick={handleStop}
            aria-label={t('redesign.home.radioStopAria')}
          >
            <span className="rh-radio-live-chip__dot" aria-hidden />
            <span className="rh-radio-live-chip__label">
              {t('redesign.home.radioActiveBadge')}
            </span>
          </button>
        ) : null}
      </div>

      <AmbientStage
        coverUrl={heroCover ?? undefined}
        className="rh-radio-hero"
      >
        <div className="rh-radio-hero__inner">
          <div
            className={[
              'rh-radio-stage',
              isDragging && 'rh-radio-stage--dragging',
              isSwitching && 'rh-radio-stage--switching',
            ]
              .filter(Boolean)
              .join(' ')}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerUp}
            role="group"
            aria-label={t('redesign.home.radioSwipeAria')}
          >
            {prevCover ? (
              <div
                className="rh-radio-peek rh-radio-peek--prev"
                aria-hidden
                style={{
                  opacity: Math.max(0, dragRatio) * 0.7,
                  transform: `translateX(${
                    -PEEK_DISTANCE_PX + dragX * 0.85
                  }px) scale(${0.78 + Math.max(0, dragRatio) * 0.1})`,
                }}
              >
                <img src={prevCover} alt="" />
              </div>
            ) : null}

            {nextCover ? (
              <div
                className="rh-radio-peek rh-radio-peek--next"
                aria-hidden
                style={{
                  opacity: Math.max(0, -dragRatio) * 0.7,
                  transform: `translateX(${
                    PEEK_DISTANCE_PX + dragX * 0.85
                  }px) scale(${0.78 + Math.max(0, -dragRatio) * 0.1})`,
                }}
              >
                <img src={nextCover} alt="" />
              </div>
            ) : null}

            <m.div
              className="rh-radio-disc-shell"
              animate={{
                x: dragX,
                rotate: reduceMotion ? 0 : dragX / 22,
                scale: !reduceMotion && isDragging ? 0.985 : 1,
              }}
              transition={
                isDragging
                  ? { duration: 0 }
                  : reduceMotion
                    ? TWEEN_FAST
                    : SPRING_SNAPPY
              }
            >
              <AudioRipple
                bpm={120}
                active={isLive}
                getAnalyser={getAnalyser}
                ringColor={accentColor}
                className="rh-radio-disc-ripple"
              >
                <div className="rh-radio-disc">
                  <AnimatePresence initial={false} mode="wait">
                    <m.div
                      key={currentTrack?.id ?? 'empty'}
                      className="rh-radio-disc-slide"
                      initial={
                        reduceMotion
                          ? { opacity: 0 }
                          : {
                              opacity: 0,
                              x: slideDirection * 140,
                              scale: 0.86,
                              filter: 'blur(8px)',
                            }
                      }
                      animate={{
                        opacity: 1,
                        x: 0,
                        scale: 1,
                        filter: 'blur(0px)',
                      }}
                      exit={
                        reduceMotion
                          ? { opacity: 0 }
                          : {
                              opacity: 0,
                              x: slideDirection * -140,
                              scale: 0.86,
                              filter: 'blur(8px)',
                            }
                      }
                      transition={
                        reduceMotion ? TWEEN_FAST : SPRING_GENTLE
                      }
                    >
                      {heroCover ? (
                        <KenBurnsCover
                          src={heroCover}
                          alt=""
                          active={isLive}
                          motion="breathe"
                          duration={22}
                        />
                      ) : (
                        <div className="rh-radio-disc-placeholder">
                          <Icon name="radio" size={48} />
                        </div>
                      )}
                    </m.div>
                  </AnimatePresence>
                </div>
              </AudioRipple>
            </m.div>
          </div>

          <div className="rh-radio-meta">
            <AnimatePresence initial={false} mode="wait">
              <m.div
                key={currentTrack?.id ?? 'empty-meta'}
                className="rh-radio-meta__body"
                initial={
                  reduceMotion ? { opacity: 0 } : { opacity: 0, y: 8 }
                }
                animate={{ opacity: 1, y: 0 }}
                exit={
                  reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8 }
                }
                transition={TWEEN_FAST}
              >
                <h2 className="rh-radio-meta__title">
                  {currentTrack?.title ?? '—'}
                </h2>
                <p className="rh-radio-meta__artist">
                  {currentTrack?.artist ?? t('redesign.home.radioPickTrack')}
                </p>
              </m.div>
            </AnimatePresence>
          </div>

          <div
            className={[
              'rh-radio-spectrum',
              isLive && 'rh-radio-spectrum--live',
            ]
              .filter(Boolean)
              .join(' ')}
            aria-hidden
          >
            <Waveform
              overlay
              variant="radio"
              height={64}
              bars={36}
              className="rh-radio-spectrum__bars"
            />
          </div>

          <div className="rh-radio-transport">
            <button
              type="button"
              className="rh-radio-transport__btn"
              onClick={() => void handleSwipe('previous')}
              disabled={!currentTrack}
              aria-label="Назад"
            >
              <Icon name="skip-back" size={20} />
            </button>
            <button
              type="button"
              className="rh-radio-transport__play"
              onClick={() => {
                if (!currentTrack) return
                haptic('light')
                void togglePlay()
              }}
              disabled={!currentTrack}
              aria-label={isPlaying ? 'Пауза' : 'Воспроизвести'}
            >
              <MorphIcon
                name={isPlaying ? 'pause' : 'play'}
                filled
                size={26}
              />
            </button>
            <button
              type="button"
              className="rh-radio-transport__btn"
              onClick={() => void handleSwipe('next')}
              disabled={!currentTrack}
              aria-label="Вперёд"
            >
              <Icon name="skip-forward" size={20} />
            </button>
          </div>
        </div>
      </AmbientStage>

      {!radioMode && currentTrack ? (
        <div className="rh-radio-cta">
          <MotionPress
            variant="primary"
            className="rh-radio-start"
            onClick={() => {
              void handleStartRadio()
            }}
          >
            <Icon name="radio" size={18} />
            <span>{t('redesign.home.radioStart')}</span>
          </MotionPress>
        </div>
      ) : null}

      {radioMode && nextTrack ? (
        <div
          className="rh-radio-next-card glass--liquid"
          role="button"
          tabIndex={0}
          onClick={() => {
            haptic('light')
            void playTrack(nextTrack)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              void playTrack(nextTrack)
            }
          }}
        >
          <div className="rh-radio-next-card__cover" aria-hidden>
            {nextCover ? (
              <img src={nextCover} alt="" />
            ) : (
              <Icon name="radio" size={22} />
            )}
          </div>
          <div className="rh-radio-next-card__body">
            <span className="rh-radio-next-card__label">
              {t('redesign.home.radioNextTrack')}
            </span>
            <span className="rh-radio-next-card__title">
              {nextTrack.title}
            </span>
            <span className="rh-radio-next-card__artist">
              {nextTrack.artist ?? '—'}
            </span>
          </div>
          <Icon name="skip-forward" size={18} />
        </div>
      ) : null}

      {historyTracks.length > 0 && (
        <>
          <div className="rh-home-section-head rh-radio-history-head">
            <span className="rh-home-section-head__title">
              {t('redesign.home.radioHistory')}
            </span>
          </div>
          <TrackList tracks={historyTracks} emptyMessage="" />
        </>
      )}

      {!currentTrack && (
        <p className="rh-radio-hint-paragraph">
          {t('redesign.home.radioPickTrack')}
        </p>
      )}
    </section>
  )
}
