import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { HorizontalSnap } from '@/components/ui/HorizontalSnap'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  m,
  TWEEN_FAST,
  TWEEN_SLOW,
  useReducedMotion,
} from '@/lib/motion'

import type { RecapSnapshotMock } from './recapMock'

const SLIDE_MS = 5000
const SLIDE_COUNT = 9

const SLIDE_VARIANTS = {
  initial: { opacity: 0, y: 22 },
  animate: {
    opacity: 1,
    y: 0,
    transition: TWEEN_SLOW,
  },
  exit: {
    opacity: 0,
    y: -14,
    transition: TWEEN_FAST,
  },
}

export interface RecapStoryStageProps {
  snapshot: RecapSnapshotMock
  onOpenShare: () => void
  onOpenAchievements: () => void
}

export function RecapStoryStage({
  snapshot,
  onOpenShare,
  onOpenAchievements,
}: RecapStoryStageProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const [slideIdx, setSlideIdx] = useState(0)
  const [prog01, setProg01] = useState(0)
  const [holdPause, setHoldPause] = useState(false)
  const slideStartMs = useRef(Date.now())
  const pauseBeganRef = useRef<number | null>(null)
  const longPressTimer = useRef<number | null>(
    null,
  )
  const pointerDownAt = useRef(0)

  const isLast = slideIdx >= SLIDE_COUNT - 1

  useEffect(() => {
    slideStartMs.current = Date.now()
    pauseBeganRef.current = null
    setProg01(0)
  }, [slideIdx])

  useEffect(() => {
    if (holdPause) {
      pauseBeganRef.current = Date.now()
    } else if (pauseBeganRef.current != null) {
      slideStartMs.current +=
        Date.now() - pauseBeganRef.current
      pauseBeganRef.current = null
    }
  }, [holdPause])

  useEffect(() => {
    if (reduce || holdPause || isLast) {
      if (reduce) {
        setProg01(1)
      }
      return
    }
    const id = window.setInterval(() => {
      const p =
        (Date.now() - slideStartMs.current) /
        SLIDE_MS
      if (p >= 1) {
        setSlideIdx((i) => Math.min(SLIDE_COUNT - 1, i + 1))
      } else {
        setProg01(p)
      }
    }, 40)
    return () => window.clearInterval(id)
  }, [reduce, holdPause, isLast, slideIdx])

  const goPrev = useCallback(() => {
    setSlideIdx((i) => Math.max(0, i - 1))
  }, [])

  const goNext = useCallback(() => {
    setSlideIdx((i) => Math.min(SLIDE_COUNT - 1, i + 1))
  }, [])

  const clearLongPress = () => {
    if (longPressTimer.current !== null) {
      window.clearTimeout(longPressTimer.current)
      longPressTimer.current = null
    }
  }

  const onPointerDown = () => {
    pointerDownAt.current = Date.now()
    clearLongPress()
    longPressTimer.current = window.setTimeout(
      () => {
        setHoldPause(true)
      },
      450,
    )
  }

  const onPointerUp = (
    e: React.PointerEvent<HTMLDivElement>,
  ) => {
    clearLongPress()
    setHoldPause(false)
    const short = Date.now() - pointerDownAt.current < 320
    if (!short) return
    const rect = e.currentTarget.getBoundingClientRect()
    const rel = (e.clientX - rect.left) / rect.width
    if (rel < 0.36) {
      goPrev()
    } else if (rel > 0.64) {
      goNext()
    }
  }

  const onPointerCancel = () => {
    clearLongPress()
    setHoldPause(false)
  }

  const pillFill = (i: number) => {
    if (i < slideIdx) return 1
    if (i > slideIdx) return 0
    if (reduce) return 1
    return prog01
  }

  const maxMood = Math.max(
    1,
    ...snapshot.moodByDaypart.map((row) => row.hours),
  )
  const maxFriends = Math.max(
    snapshot.friendsYouHours,
    snapshot.friendsAvgHours,
    1,
  )

  const renderSlide = () => {
    switch (slideIdx) {
      case 0:
        return (
          <m.div
            key="s0"
            className="rh-recap-slide rh-recap-slide--center"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <p className="rh-recap-kicker">
              {t('redesign.recap.introKicker')}
            </p>
            <h1 className="rh-recap-lt">
              {t('redesign.recap.introTitle')}
            </h1>
            <p className="rh-recap-sub">
              {t('redesign.recap.introSub', {
                label: snapshot.yearLabel,
              })}
            </p>
          </m.div>
        )
      case 1:
        return (
          <m.div
            key="s1"
            className="rh-recap-slide rh-recap-slide--center"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <p className="rh-recap-kicker">
              {t('redesign.recap.minutesKicker')}
            </p>
            <m.p
              className="rh-recap-mega"
              animate={
                reduce
                  ? undefined
                  : { scale: [1, 1.04, 1] }
              }
              transition={{
                duration: 2.2,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              {snapshot.totalMinutes}
            </m.p>
            <p className="rh-recap-sub">
              {t('redesign.recap.minutesUnit')}
            </p>
          </m.div>
        )
      case 2:
        return (
          <m.div
            key="s2"
            className="rh-recap-slide"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <p className="rh-recap-kicker">
              {t('redesign.recap.artistsKicker')}
            </p>
            <div className="rh-recap-snap">
              <HorizontalSnap
                items={snapshot.topArtists}
                pageDots
                parallax
                ariaLabel={t('redesign.recap.artistsAria')}
                renderItem={(a) => (
                  <div className="rh-recap-artist-card">
                    <div className="rh-recap-artist-av">
                      <img src={a.coverUrl} alt="" />
                    </div>
                    <p className="rh-recap-artist-name">
                      {a.name}
                    </p>
                    <p className="rh-recap-artist-plays">
                      {t('redesign.recap.artistPlays', {
                        n: a.plays,
                      })}
                    </p>
                  </div>
                )}
              />
            </div>
          </m.div>
        )
      case 3:
        return (
          <m.div
            key="s3"
            className="rh-recap-slide"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <p className="rh-recap-kicker">
              {t('redesign.recap.tracksKicker')}
            </p>
            <div className="rh-recap-stack">
              {snapshot.topTracks.map((tr, i) => (
                <div
                  key={`${tr.title}-${String(i)}`}
                  className="rh-recap-stack-item"
                  style={{ zIndex: 10 - i }}
                >
                  <BeatPulse bpm={tr.bpm} active>
                    <div className="rh-recap-stack-cover">
                      <KenBurnsCover
                        src={tr.coverUrl}
                        alt=""
                        duration={14 + i * 2}
                      />
                    </div>
                  </BeatPulse>
                </div>
              ))}
            </div>
          </m.div>
        )
      case 4: {
        const mp = snapshot.mostPlayed
        return (
          <m.div
            key="s4"
            className="rh-recap-slide rh-recap-slide--fill"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <AmbientStage
              coverUrl={mp.coverUrl}
              className="rh-recap-ambient"
            >
              <div className="rh-recap-ambient-inner">
                <BeatPulse bpm={mp.bpm} active>
                  <div className="rh-recap-hero-cover">
                    <KenBurnsCover
                      src={mp.coverUrl}
                      alt=""
                      duration={16}
                    />
                  </div>
                </BeatPulse>
                <div className="rh-recap-ambient-meta">
                  <p className="rh-recap-kicker">
                    {t('redesign.recap.topTrackKicker')}
                  </p>
                  <p className="rh-recap-track-title">
                    {mp.title}
                  </p>
                  <p className="rh-recap-track-artist">
                    {mp.artist}
                  </p>
                </div>
              </div>
            </AmbientStage>
          </m.div>
        )
      }
      case 5:
        return (
          <m.div
            key="s5"
            className="rh-recap-slide"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <p className="rh-recap-kicker">
              {t('redesign.recap.genresKicker')}
            </p>
            <ul className="rh-recap-bars">
              {snapshot.genres.map((g) => (
                <li key={g.label} className="rh-recap-bar-row">
                  <span className="rh-recap-bar-label">
                    {g.label}
                  </span>
                  <div className="rh-recap-bar-track">
                    <m.span
                      className="rh-recap-bar-fill"
                      initial={{
                        scaleX: reduce ? 1 : 0,
                      }}
                      animate={{
                        scaleX: 1,
                      }}
                      transition={
                        reduce
                          ? { duration: 0 }
                          : {
                              delay: 0.06,
                              duration: 0.55,
                              ease: [0.22, 0.61, 0.36, 1],
                            }
                      }
                      style={{
                        transformOrigin: '0 50%',
                        width: `${Math.round(g.share01 * 100)}%`,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </m.div>
        )
      case 6:
        return (
          <m.div
            key="s6"
            className="rh-recap-slide"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <p className="rh-recap-kicker">
              {t('redesign.recap.moodKicker')}
            </p>
            <ul className="rh-recap-mood">
              {snapshot.moodByDaypart.map((row) => (
                <li
                  key={row.labelKey}
                  className="rh-recap-mood-row"
                >
                  <span>
                    {t(
                      `redesign.recap.mood.${row.labelKey}`,
                    )}
                  </span>
                  <div className="rh-recap-mood-track">
                    <m.span
                      className="rh-recap-mood-fill"
                      initial={{
                        scaleX: reduce ? 1 : 0,
                      }}
                      animate={{ scaleX: 1 }}
                      transition={
                        reduce
                          ? { duration: 0 }
                          : {
                              duration: 0.48,
                              ease: [0.22, 0.61, 0.36, 1],
                            }
                      }
                      style={{
                        transformOrigin: '0 50%',
                        width: `${Math.round((row.hours / maxMood) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="rh-recap-mood-h">
                    {t('redesign.recap.moodHours', {
                      n: row.hours,
                    })}
                  </span>
                </li>
              ))}
            </ul>
          </m.div>
        )
      case 7:
        return (
          <m.div
            key="s7"
            className="rh-recap-slide"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <p className="rh-recap-kicker">
              {t('redesign.recap.friendsKicker')}
            </p>
            <p className="rh-recap-sub">
              {t(
                `redesign.recap.${snapshot.friendsHeadlineKey}`,
              )}
            </p>
            <div className="rh-recap-friends">
              <div className="rh-recap-friends-row">
                <span>{t('redesign.recap.friendsYou')}</span>
                <div className="rh-recap-mood-track">
                  <m.span
                    className="rh-recap-mood-fill"
                    initial={{
                      scaleX: reduce ? 1 : 0,
                    }}
                    animate={{ scaleX: 1 }}
                    transition={
                      reduce
                        ? { duration: 0 }
                        : { duration: 0.5 }
                    }
                    style={{
                      transformOrigin: '0 50%',
                      width: `${Math.round((snapshot.friendsYouHours / maxFriends) * 100)}%`,
                    }}
                  />
                </div>
                <span>
                  {t('redesign.recap.friendsHours', {
                    n: snapshot.friendsYouHours,
                  })}
                </span>
              </div>
              <div className="rh-recap-friends-row">
                <span>{t('redesign.recap.friendsAvg')}</span>
                <div className="rh-recap-mood-track">
                  <m.span
                    className="rh-recap-mood-fill rh-recap-mood-fill--muted"
                    initial={{
                      scaleX: reduce ? 1 : 0,
                    }}
                    animate={{ scaleX: 1 }}
                    transition={
                      reduce
                        ? { duration: 0 }
                        : { duration: 0.5, delay: 0.08 }
                    }
                    style={{
                      transformOrigin: '0 50%',
                      width: `${Math.round((snapshot.friendsAvgHours / maxFriends) * 100)}%`,
                    }}
                  />
                </div>
                <span>
                  {t('redesign.recap.friendsHours', {
                    n: snapshot.friendsAvgHours,
                  })}
                </span>
              </div>
            </div>
          </m.div>
        )
      default:
        return (
          <m.div
            key="s8"
            className="rh-recap-slide rh-recap-slide--center"
            variants={SLIDE_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <h2 className="rh-recap-lt">
              {t('redesign.recap.outroTitle')}
            </h2>
            <p className="rh-recap-sub">
              {t('redesign.recap.outroSub')}
            </p>
            <div
              className="rh-recap-outro-actions"
              onPointerDown={(e) =>
                e.stopPropagation()
              }
              onPointerUp={(e) =>
                e.stopPropagation()
              }
            >
              <MotionPress
                variant="primary"
                className="rh-recap-outro-share"
                onClick={onOpenShare}
              >
                {t('redesign.recap.outroShare')}
              </MotionPress>
              <MotionPress
                variant="ghost"
                className="rh-recap-outro-ach"
                onClick={onOpenAchievements}
              >
                {t('redesign.recap.outroAchievements')}
              </MotionPress>
            </div>
          </m.div>
        )
    }
  }

  return (
    <div className="rh-recap-stage">
      <header className="rh-recap-top">
        <MotionPress
          variant="ghost"
          className="rh-recap-close"
          aria-label={t('redesign.recap.closeAria')}
          onClick={() => navigate(-1)}
        >
          <Icon name="x" size={22} />
        </MotionPress>
        <div className="rh-recap-pills" aria-hidden>
          {Array.from({ length: SLIDE_COUNT }).map((_, i) => (
            <div key={String(i)} className="rh-recap-pill">
              <m.div
                className="rh-recap-pill-fill"
                initial={false}
                animate={{ scaleX: pillFill(i) }}
                transition={{
                  duration: reduce ? 0 : 0.04,
                  ease: 'linear',
                }}
                style={{ transformOrigin: '0 50%' }}
              />
            </div>
          ))}
        </div>
      </header>
      <div
        className="rh-recap-touch"
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        onPointerLeave={onPointerCancel}
      >
        <AnimatePresence mode="wait">
          {renderSlide()}
        </AnimatePresence>
      </div>
    </div>
  )
}
