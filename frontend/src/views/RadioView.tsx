import {
  type PointerEvent as ReactPointerEvent,
  useEffect,
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
import { BeatPulse } from '@/components/ui/BeatPulse'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { api } from '@/lib/api'
import { getPrefetchManager } from '@/lib/prefetch/PrefetchManager'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerPlayback,
} from '@/store/PlayerContext'
import {
  m,
  SPRING_BOUNCY,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import type { Track } from '@/types/api'

function coverUrl(key: string | null): string | null {
  if (!key) return null
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

// TODO(radio-moods): restore when mood-tagged radio API is ready.
// const MOOD_ICONS = [
//   'heart',
//   'search',
//   'flame',
//   'star',
//   'radio',
//   'bookmark',
// ] as const

const DISC_SWIPE_THRESHOLD_PX = 42
const DISC_SWIPE_MAX_OFFSET_PX = 92
const DISC_SLIDE_DISTANCE_PX = 160
const DISC_TAP_MAX_OFFSET_PX = 6
const RADIO_WAVE_STYLE: 'style1' | 'style2' | 'style3' =
  'style2'

export function RadioView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { track: currentTrack, queue } = usePlayerMeta()
  const { isPlaying } = usePlayerPlayback()
  const {
    playNext,
    playTrack,
    togglePlay,
    startRadio,
    stopRadio,
    radioMode,
  } = usePlayerActions()

  const [historyTracks, setHistoryTracks] = useState<Track[]>([])
  const [slideDirection, setSlideDirection] = useState(1)
  const [isSwitching, setIsSwitching] = useState(false)
  const [discDragX, setDiscDragX] = useState(0)
  const [isDiscDragging, setIsDiscDragging] = useState(false)
  const [radioPreviewTracks, setRadioPreviewTracks] = useState<
    Track[]
  >([])
  const historyRef = useRef<Track[]>([])
  const switchingRef = useRef(false)
  const discPointerRef = useRef<{
    pointerId: number
    startX: number
    offsetX: number
  } | null>(null)
  const reduceMotion = useReducedMotion()

  const heroCover = currentTrack
    ? coverUrl(currentTrack.cover_key)
    : null
  const bpm = 120
  const discIsLive = radioMode && isPlaying
  const discSwipeEnabled = radioMode && Boolean(currentTrack)
  const nextTrack = queue[0] ?? radioPreviewTracks[0] ?? null
  const nextTrackCover = nextTrack
    ? coverUrl(nextTrack.cover_key)
    : null
  const nextTrackTitle = nextTrack?.title ?? '—'
  const nextTrackArtist =
    nextTrack?.artist ?? t('redesign.home.radioQueueEmpty')

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

  useEffect(() => {
    if (!radioMode || !currentTrack) {
      setRadioPreviewTracks([])
      return
    }
    let cancelled = false
    const excludeIds = [
      currentTrack.id,
      ...historyRef.current.map((track) => track.id),
      ...queue.map((track) => track.id),
    ]
    api
      .getRadio(currentTrack.id, 14, excludeIds)
      .then((res) => {
        if (cancelled) return
        const candidates = res.tracks.filter(
          (track) =>
            track.id !== currentTrack.id &&
            !queue.some((queuedTrack) => queuedTrack.id === track.id),
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
  }, [radioMode, currentTrack?.id, queue])

  const handleStartRadio = async () => {
    if (!currentTrack) return
    historyRef.current = []
    setHistoryTracks([])
    await startRadio(currentTrack)
  }

  const handleStop = () => {
    stopRadio()
  }

  // TODO(radio-moods): restore when mood-tagged radio API is ready.
  // const handleMood = (_moodId: string) => {
  //   if (!currentTrack) {
  //     showIsland({
  //       kind: 'toast',
  //       title: t('redesign.home.radioPickTrackHint'),
  //       durationMs: 3000,
  //     })
  //     return
  //   }
  //   void handleStartRadio()
  // }

  const switchToPreviousRadioTrack = async () => {
    const previousTrack =
      historyRef.current.length > 1
        ? historyRef.current[historyRef.current.length - 2]
        : null
    if (!previousTrack) return false
    historyRef.current = historyRef.current.slice(0, -1)
    setHistoryTracks([...historyRef.current].reverse())
    await playTrack(previousTrack)
    return true
  }

  const handleDiscSwipe = async (
    direction: 'next' | 'previous',
  ) => {
    if (!discSwipeEnabled || switchingRef.current) return
    switchingRef.current = true
    setIsSwitching(true)
    setSlideDirection(direction === 'next' ? 1 : -1)
    try {
      const changed =
        direction === 'next'
          ? await playNext()
          : await switchToPreviousRadioTrack()
      if (!changed) {
        showIsland({
          kind: 'toast',
          title:
            direction === 'next'
              ? t('redesign.home.radioNextUnavailable')
              : t('redesign.home.radioPrevUnavailable'),
          durationMs: 2200,
        })
      }
    } finally {
      switchingRef.current = false
      setIsSwitching(false)
    }
  }

  const handleDiscPointerDown = (
    e: ReactPointerEvent<HTMLDivElement>,
  ) => {
    if (!discSwipeEnabled || switchingRef.current) return
    discPointerRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      offsetX: 0,
    }
    setIsDiscDragging(true)
    setDiscDragX(0)
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const handleDiscPointerMove = (
    e: ReactPointerEvent<HTMLDivElement>,
  ) => {
    const pointer = discPointerRef.current
    if (!pointer || pointer.pointerId !== e.pointerId) return
    const rawOffset = e.clientX - pointer.startX
    const offset = Math.max(
      -DISC_SWIPE_MAX_OFFSET_PX,
      Math.min(DISC_SWIPE_MAX_OFFSET_PX, rawOffset),
    )
    pointer.offsetX = offset
    setDiscDragX(offset)
    if (Math.abs(offset) > 4) {
      e.preventDefault()
    }
  }

  const finishDiscPointer = (
    e: ReactPointerEvent<HTMLDivElement>,
  ) => {
    const pointer = discPointerRef.current
    if (!pointer || pointer.pointerId !== e.pointerId) return
    discPointerRef.current = null
    setIsDiscDragging(false)
    setDiscDragX(0)
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
    if (
      Math.abs(pointer.offsetX) <= DISC_TAP_MAX_OFFSET_PX &&
      radioMode &&
      currentTrack &&
      !switchingRef.current
    ) {
      togglePlay()
      return
    }
    if (pointer.offsetX <= -DISC_SWIPE_THRESHOLD_PX) {
      void handleDiscSwipe('next')
    } else if (pointer.offsetX >= DISC_SWIPE_THRESHOLD_PX) {
      void handleDiscSwipe('previous')
    }
  }

  // TODO(radio-moods): restore when mood-tagged radio API is ready.
  // const moodDefs = [
  //   {
  //     id: 'chill',
  //     labelKey: 'radioMoodChill',
  //     hintKey: 'radioMoodHintChill',
  //   },
  //   {
  //     id: 'focus',
  //     labelKey: 'radioMoodFocus',
  //     hintKey: 'radioMoodHintFocus',
  //   },
  //   {
  //     id: 'gym',
  //     labelKey: 'radioMoodGym',
  //     hintKey: 'radioMoodHintGym',
  //   },
  //   {
  //     id: 'cinematic',
  //     labelKey: 'radioMoodCinematic',
  //     hintKey: 'radioMoodHintCinematic',
  //   },
  //   {
  //     id: 'retro',
  //     labelKey: 'radioMoodRetro',
  //     hintKey: 'radioMoodHintRetro',
  //   },
  //   {
  //     id: 'acoustic',
  //     labelKey: 'radioMoodAcoustic',
  //     hintKey: 'radioMoodHintAcoustic',
  //   },
  // ]

  return (
    <section className="view active rh-radio-root">
      <div className="view-header">
        <button
          type="button"
          className="icon-btn"
          onClick={() => navigate(-1)}
          aria-label={t('redesign.home.back')}
        >
          <Icon
            name="chevron"
            size={20}
            className="back-chevron"
          />
        </button>
        <div className="rh-radio-header__meta">
          <h2>{t('redesign.home.radioTitle')}</h2>
          <span className="hint">
            {radioMode
              ? t('redesign.home.radioSubtitleOn')
              : t('redesign.home.radioSubtitleIdle')}
          </span>
        </div>
        {radioMode && (
          <button
            type="button"
            className="icon-btn"
            onClick={handleStop}
            aria-label={t('redesign.home.radioStopAria')}
            title={t('redesign.home.radioStopAria')}
          >
            <Icon name="x" size={20} />
          </button>
        )}
      </div>

      <AmbientStage
        coverUrl={heroCover ?? undefined}
        className="rh-radio-hero"
      >
        <div className="rh-radio-hero__inner">
          <div
            className={[
              'rh-radio-hero-wave-bg',
              discIsLive && 'rh-radio-hero-wave-bg--live',
              `rh-radio-hero-wave-bg--${RADIO_WAVE_STYLE}`,
            ]
              .filter(Boolean)
              .join(' ')}
            aria-hidden
          >
            <div className="rh-radio-hero-wave-gradient" />
            <Waveform
              overlay
              variant="radio"
              height={
                RADIO_WAVE_STYLE === 'style3'
                  ? 112
                  : RADIO_WAVE_STYLE === 'style2'
                    ? 102
                    : 84
              }
              bars={
                RADIO_WAVE_STYLE === 'style3'
                  ? 52
                  : RADIO_WAVE_STYLE === 'style2'
                    ? 44
                    : 36
              }
              className="rh-radio-hero-waveform"
            />
            <Waveform
              overlay
              variant="radio"
              height={
                RADIO_WAVE_STYLE === 'style3'
                  ? 92
                  : RADIO_WAVE_STYLE === 'style2'
                    ? 86
                    : 70
              }
              bars={
                RADIO_WAVE_STYLE === 'style3'
                  ? 52
                  : RADIO_WAVE_STYLE === 'style2'
                    ? 44
                    : 36
              }
              className="rh-radio-hero-waveform rh-radio-hero-waveform--reflection"
            />
          </div>
          <m.div
            className={[
              'rh-radio-disc-swipe',
              discSwipeEnabled && 'rh-radio-disc-swipe--enabled',
              isSwitching && 'rh-radio-disc-swipe--switching',
            ]
              .filter(Boolean)
              .join(' ')}
            onPointerDown={handleDiscPointerDown}
            onPointerMove={handleDiscPointerMove}
            onPointerUp={finishDiscPointer}
            onPointerCancel={finishDiscPointer}
            animate={{
              x: discDragX,
              rotate: reduceMotion ? 0 : discDragX / 18,
              scale:
                !reduceMotion && isDiscDragging ? 0.985 : 1,
            }}
            transition={
              isDiscDragging
                ? { duration: 0 }
                : reduceMotion
                  ? TWEEN_FAST
                  : SPRING_BOUNCY
            }
            aria-label={t('redesign.home.radioSwipeAria')}
            role="group"
          >
            <BeatPulse
              bpm={bpm}
              active={discIsLive}
              className="rh-radio-disc-pulse"
            >
              <div className="rh-radio-disc-viewport">
                <AnimatePresence initial={false} mode="wait">
                  <m.div
                    key={currentTrack?.id ?? 'empty'}
                    className="rh-radio-disc-slide"
                    initial={
                      reduceMotion
                        ? { opacity: 0 }
                        : {
                            opacity: 0,
                            x:
                              slideDirection *
                              DISC_SLIDE_DISTANCE_PX,
                            scale: 0.88,
                            rotate: slideDirection * 8,
                            filter: 'blur(10px)',
                          }
                    }
                    animate={{
                      opacity: 1,
                      x: 0,
                      scale: 1,
                      rotate: 0,
                      filter: 'blur(0px)',
                    }}
                    exit={
                      reduceMotion
                        ? { opacity: 0 }
                        : {
                            opacity: 0,
                            x:
                              slideDirection *
                              -DISC_SLIDE_DISTANCE_PX,
                            scale: 0.88,
                            rotate: slideDirection * -8,
                            filter: 'blur(10px)',
                          }
                    }
                    transition={
                      reduceMotion ? TWEEN_FAST : SPRING_GENTLE
                    }
                  >
                    <div className="rh-radio-disc-wrap">
                      {heroCover ? (
                        <KenBurnsCover
                          src={heroCover}
                          alt=""
                          active={discIsLive}
                        />
                      ) : (
                        <div className="rh-radio-disc-placeholder">
                          <Icon name="radio" size={48} />
                        </div>
                      )}
                    </div>
                  </m.div>
                </AnimatePresence>
              </div>
            </BeatPulse>
          </m.div>
          <div className="rh-radio-hero__meta">
            <h2>
              {currentTrack?.title ?? '—'}
            </h2>
            <span className="hint">
              {radioMode
                ? t('redesign.home.radioSubtitleOn')
                : t('redesign.home.radioSubtitleIdle')}
            </span>
          </div>
        </div>
      </AmbientStage>

      <div className="rh-radio-controls">
        {!radioMode ? (
          <MotionPress
            variant="primary"
            className="rh-radio-start"
            onClick={() => {
              void handleStartRadio()
            }}
            disabled={!currentTrack}
          >
            <Icon name="radio" size={18} />
            <span>
              {currentTrack
                ? t('redesign.home.radioStart')
                : t('redesign.home.radioPickTrack')}
            </span>
          </MotionPress>
        ) : (
          <div className="rh-radio-active-bar">
            <span className="player-radio-badge player-radio-badge--active">
              <span className="player-radio-badge__dot" />
              {t('redesign.home.radioActiveBadge')}
            </span>
            <span className="rh-radio-active-bar__meta">
              {currentTrack?.title ?? '—'}
            </span>
            <MotionPress
              variant="icon"
              ariaLabel={t('redesign.home.radioStopAria')}
              onClick={handleStop}
            >
              <Icon name="x" size={16} />
            </MotionPress>
          </div>
        )}
      </div>

      <div className="rh-radio-next-card glass--liquid">
        <div className="rh-radio-next-card__cover" aria-hidden>
          {nextTrackCover ? (
            <img src={nextTrackCover} alt="" />
          ) : (
            <Icon name="radio" size={22} />
          )}
        </div>
        <div className="rh-radio-next-card__body">
          <span className="rh-radio-next-card__label">
            {t('redesign.home.radioNextTrack')}
          </span>
          <span className="rh-radio-next-card__title">
            {nextTrackTitle}
          </span>
          <span className="rh-radio-next-card__artist">
            {nextTrackArtist}
          </span>
        </div>
      </div>

      {/*
        TODO(radio-moods): restore this section when mood-tagged
        radio API is ready.

        <div className="rh-radio-moods">
          <div className="rh-radio-moods__title">
            {t('redesign.home.radioMoodsTitle')}
          </div>
          <div className="rh-radio-moods__grid">
            {moodDefs.map((mood, idx) => (
              <MotionPress
                key={mood.id}
                variant="subtle"
                className="rh-radio-mood-card glass--liquid"
                onClick={() => handleMood(mood.id)}
              >
                <span className="rh-radio-mood-card__icon" aria-hidden>
                  <MorphIcon
                    name={MOOD_ICONS[idx]}
                    filled
                    size={22}
                  />
                </span>
                <span className="rh-radio-mood-card__label">
                  {t(`redesign.home.${mood.labelKey}`)}
                </span>
                <span className="rh-radio-mood-card__hint">
                  {t(`redesign.home.${mood.hintKey}`)}
                </span>
              </MotionPress>
            ))}
          </div>
        </div>
      */}

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

      {!radioMode && !currentTrack && (
        <p className="rh-radio-hint-paragraph">
          {t('redesign.home.radioPickTrack')}
        </p>
      )}
    </section>
  )
}
