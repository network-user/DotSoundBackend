import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import {
  type PanInfo,
  useMotionValue,
  useTransform,
} from 'framer-motion'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  m,
  SPRING_GENTLE,
  SPRING_SNAPPY,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { showIsland } from '@/lib/island'
import { trackActivationEvent } from '@/lib/activation'
import { hapticSelection } from '@/lib/telegram'
import { useOnboardingAudio } from '@/hooks/useOnboardingAudio'
import { AvatarBuilder } from '@/components/Onboarding/AvatarBuilder'
import { GenreBubble } from '@/components/Onboarding/GenreBubble'
import type {
  OnboardingBootstrap,
  OnboardingTasteDecision,
  OnboardingGenrePreviewResponse,
  Track,
} from '@/types/api'

interface Props {
  onComplete: () => void
}

type Step =
  | 'welcome'
  | 'profile'
  | 'genres'
  | 'swipe'
  | 'complete'

const MIN_GENRES = 3
const SWIPE_BATCH = 5
const SWIPE_THRESHOLD = 110

const GENRE_SILENT_WAV =
  'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA'

const STEP_ORDER: Step[] = [
  'welcome',
  'profile',
  'genres',
  'swipe',
  'complete',
]

const PROGRESS_STEPS: Step[] = [
  'profile',
  'genres',
  'swipe',
]

export function OnboardingV2({ onComplete }: Props) {
  const { t } = useTranslation()
  const reduce = Boolean(useReducedMotion())

  const [step, setStep] = useState<Step>('welcome')
  const [bootstrap, setBootstrap] =
    useState<OnboardingBootstrap | null>(null)
  const [bootstrapErr, setBootstrapErr] = useState<
    string | null
  >(null)
  const [saving, setSaving] = useState(false)

  const [displayName, setDisplayName] = useState('')
  const [useDefaultAvatar, setUseDefaultAvatar] =
    useState(false)
  const [profileErr, setProfileErr] = useState<
    string | null
  >(null)

  const [selectedGenres, setSelectedGenres] = useState<
    string[]
  >([])

  const [tasteTracks, setTasteTracks] = useState<
    Track[]
  >([])
  const [tasteIndex, setTasteIndex] = useState(0)
  const [tasteDecisions, setTasteDecisions] = useState<
    {
      track_id: number
      decision: OnboardingTasteDecision
    }[]
  >([])
  const [tasteLoading, setTasteLoading] = useState(false)

  const audio = useOnboardingAudio()
  const lastFetchCountRef = useRef(0)
  const autoPlayedTrackRef = useRef<number | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .getOnboardingBootstrap()
      .then((b) => {
        if (cancelled) return
        setBootstrap(b)
        setDisplayName(
          b.profile_defaults.current_display_name ??
            b.profile_defaults.suggested_display_name ??
            '',
        )
      })
      .catch(() => {
        if (cancelled) return
        setBootstrapErr('bootstrap_failed')
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    trackActivationEvent('onboarding_step_view', {
      meta: { step },
    })
  }, [step])

  useEffect(() => {
    if (step !== 'swipe' || tasteTracks.length > 0) {
      return
    }
    let cancelled = false
    setTasteLoading(true)
    api
      .getTasteSwipeTracks(SWIPE_BATCH)
      .then((tracks) => {
        if (cancelled) return
        setTasteTracks(tracks)
        setTasteIndex(0)
      })
      .catch(() => {
        if (cancelled) return
        showIsland({
          kind: 'error',
          title: t(
            'redesign.onboardingMsg.saveFail',
          ),
          durationMs: 3000,
        })
      })
      .finally(() => {
        if (!cancelled) setTasteLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [step, tasteTracks.length, t])

  const goNext = useCallback((from: Step) => {
    const i = STEP_ORDER.indexOf(from)
    if (i < 0 || i >= STEP_ORDER.length - 1) return
    setStep(STEP_ORDER[i + 1])
  }, [])

  const goBack = useCallback(() => {
    const i = STEP_ORDER.indexOf(step)
    if (i <= 0) return
    if (step === 'swipe') {
      audio.stop()
      setTasteTracks([])
      setTasteIndex(0)
      setTasteDecisions([])
      lastFetchCountRef.current = 0
      autoPlayedTrackRef.current = null
    }
    setStep(STEP_ORDER[i - 1])
  }, [step, audio])

  const handleWelcomeStart = () => {
    hapticSelection()
    audio.prime()
    goNext('welcome')
  }

  const handleProfileSubmit = async () => {
    if (saving) return
    const name = displayName.trim()
    if (name.length < 1 || name.length > 64) {
      setProfileErr(
        t('redesign.onboardingV2.profile.errInvalid'),
      )
      return
    }
    setProfileErr(null)
    setSaving(true)
    try {
      const res = await api.submitOnboardingProfile({
        display_name: name,
        locale:
          bootstrap?.profile_defaults.locale ?? null,
        use_default_avatar: useDefaultAvatar,
      })
      trackActivationEvent('onboarding_step_complete', {
        meta: {
          step: 'profile',
          has_name: Boolean(res.display_name),
        },
      })
      goNext('profile')
    } catch {
      setProfileErr(
        t('redesign.onboardingV2.profile.errSave'),
      )
    } finally {
      setSaving(false)
    }
  }

  const handleProfileSkip = () => {
    hapticSelection()
    goNext('profile')
  }

  const toggleGenre = (g: string) => {
    setSelectedGenres((prev) =>
      prev.includes(g)
        ? prev.filter((x) => x !== g)
        : [...prev, g],
    )
  }

  const handleGenresSubmit = async () => {
    if (
      saving ||
      selectedGenres.length < MIN_GENRES
    ) {
      return
    }
    audio.prime()
    setSaving(true)
    try {
      await api.saveOnboardingPreferences({
        genres: selectedGenres,
        artist_ids: [],
        moods: [],
      })
      trackActivationEvent('onboarding_step_complete', {
        meta: {
          step: 'genres',
          count: selectedGenres.length,
        },
      })
      showIsland({
        kind: 'toast',
        title: t(
          'redesign.onboardingMsg.genresDone',
          { count: selectedGenres.length },
        ),
        durationMs: 2400,
      })
      goNext('genres')
    } catch {
      showIsland({
        kind: 'error',
        title: t('redesign.onboardingMsg.saveFail'),
        durationMs: 3000,
      })
    } finally {
      setSaving(false)
    }
  }

  const recordDecision = useCallback(
    (decision: OnboardingTasteDecision) => {
      const tr = tasteTracks[tasteIndex]
      if (!tr) return
      hapticSelection()
      setTasteDecisions((prev) => [
        ...prev,
        { track_id: tr.id, decision },
      ])
      setTasteIndex((i) => i + 1)
    },
    [tasteTracks, tasteIndex],
  )

  const togglePreview = useCallback(() => {
    audio.toggle({ step: 'swipe' })
  }, [audio])

  const finalizeSwipe = useCallback(
    async (decisions: typeof tasteDecisions) => {
      if (saving) return
      setSaving(true)
      try {
        if (decisions.length > 0) {
          await api.saveTasteSwipeBatch(decisions)
        }
        await api.completeOnboarding()
        trackActivationEvent('onboarding_complete', {
          meta: { calibrated: decisions.length },
        })
        showIsland({
          kind: 'toast',
          title: t(
            'redesign.onboardingMsg.calibrationDone',
          ),
          durationMs: 2400,
        })
        goNext('swipe')
      } catch {
        showIsland({
          kind: 'error',
          title: t(
            'redesign.onboardingMsg.finishFail',
          ),
          durationMs: 3000,
        })
      } finally {
        setSaving(false)
      }
    },
    [saving, goNext, t],
  )

  useEffect(() => {
    if (step !== 'swipe') return
    if (tasteTracks.length === 0) return
    if (tasteIndex < tasteTracks.length) return
    if (lastFetchCountRef.current === tasteTracks.length)
      return
    lastFetchCountRef.current = tasteTracks.length

    let cancelled = false
    setTasteLoading(true)
    api
      .getTasteSwipeTracks(SWIPE_BATCH)
      .then((tracks) => {
        if (cancelled) return
        const seenIds = new Set(
          tasteTracks.map((t) => t.id),
        )
        const fresh = tracks.filter(
          (t) => !seenIds.has(t.id),
        )
        if (fresh.length > 0) {
          setTasteTracks((prev) => [...prev, ...fresh])
        } else {
          // Server returned only duplicates — reset guard
          // so the next swipe triggers a retry instead of
          // freezing with an empty card stack.
          lastFetchCountRef.current = 0
        }
      })
      .catch(() => {
        lastFetchCountRef.current = 0
      })
      .finally(() => {
        if (!cancelled) setTasteLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [step, tasteIndex, tasteTracks])

  useEffect(() => {
    if (step !== 'swipe') return
    const tr = tasteTracks[tasteIndex]
    if (!tr) return
    if (autoPlayedTrackRef.current === tr.id) return
    autoPlayedTrackRef.current = tr.id
    audio.playTrack(
      tr.id,
      `/api/v1/track-preview/${tr.id}/segment.mp4`,
      { step: 'swipe' },
    )
  }, [step, tasteIndex, tasteTracks, audio])

  const canFinish =
    tasteDecisions.length >= SWIPE_BATCH

  const handleManualFinish = useCallback(() => {
    hapticSelection()
    void finalizeSwipe(tasteDecisions)
  }, [tasteDecisions, finalizeSwipe])

  const handleCompleteFinish = useCallback(
    (openImport: boolean) => {
      hapticSelection()
      onComplete()
      if (openImport) {
        try {
          window.location.assign(
            '/mini_app/profile?import=1',
          )
        } catch {
          /* ignore */
        }
      }
    },
    [onComplete],
  )

  const progressIndex = useMemo(() => {
    return PROGRESS_STEPS.indexOf(step)
  }, [step])

  return (
    <div className="onb-v2-shell">
      <ProgressBar
        steps={PROGRESS_STEPS.length}
        currentIndex={progressIndex}
      />


      <div className="onb-v2-content">
        <AnimatePresence mode="wait">
          {step === 'welcome' && (
            <m.div
              key="welcome"
              initial={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, y: 8 }
              }
              animate={
                reduce
                  ? { opacity: 1 }
                  : { opacity: 1, y: 0 }
              }
              exit={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, y: -8 }
              }
              transition={
                reduce ? TWEEN_FAST : SPRING_GENTLE
              }
              className="onb-v2-step"
            >
              <WelcomeStep
                onStart={handleWelcomeStart}
              />
            </m.div>
          )}

          {step === 'profile' && bootstrap && (
            <m.div
              key="profile"
              initial={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, x: 8 }
              }
              animate={
                reduce
                  ? { opacity: 1 }
                  : { opacity: 1, x: 0 }
              }
              exit={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, x: -8 }
              }
              transition={
                reduce ? TWEEN_FAST : SPRING_GENTLE
              }
              className="onb-v2-step"
            >
              <ProfileStep
                bootstrap={bootstrap}
                displayName={displayName}
                onChangeName={setDisplayName}
                onUseDefaultAvatar={() =>
                  setUseDefaultAvatar(true)
                }
                onResetUseDefault={() =>
                  setUseDefaultAvatar(false)
                }
                err={profileErr}
              />
            </m.div>
          )}

          {step === 'genres' && bootstrap && (
            <m.div
              key="genres"
              initial={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, x: 8 }
              }
              animate={
                reduce
                  ? { opacity: 1 }
                  : { opacity: 1, x: 0 }
              }
              exit={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, x: -8 }
              }
              transition={
                reduce ? TWEEN_FAST : SPRING_GENTLE
              }
              className="onb-v2-step"
            >
              <GenresStep
                bubbles={bootstrap.genre_bubbles}
                selected={selectedGenres}
                onToggle={toggleGenre}
              />
            </m.div>
          )}

          {step === 'swipe' && (
            <m.div
              key="swipe"
              initial={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, x: 8 }
              }
              animate={
                reduce
                  ? { opacity: 1 }
                  : { opacity: 1, x: 0 }
              }
              exit={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, x: -8 }
              }
              transition={
                reduce ? TWEEN_FAST : SPRING_GENTLE
              }
              className="onb-v2-step"
            >
              <SwipeStep
                tracks={tasteTracks}
                index={tasteIndex}
                loading={tasteLoading}
                playingId={
                  audio.state === 'playing'
                    ? audio.currentTrackId
                    : null
                }
                audioBlocked={
                  audio.state === 'blocked'
                }
                onLike={() => recordDecision('like')}
                onDislike={() =>
                  recordDecision('dislike')
                }
                onSkipCard={() =>
                  recordDecision('skip')
                }
                onTogglePreview={togglePreview}
                reduce={reduce}
              />
            </m.div>
          )}

          {step === 'complete' && bootstrap && (
            <m.div
              key="complete"
              initial={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, scale: 0.96 }
              }
              animate={
                reduce
                  ? { opacity: 1 }
                  : { opacity: 1, scale: 1 }
              }
              exit={
                reduce
                  ? { opacity: 0 }
                  : { opacity: 0, scale: 0.98 }
              }
              transition={
                reduce ? TWEEN_FAST : SPRING_GENTLE
              }
              className="onb-v2-step"
            >
              <CompleteStep
                showImport={
                  bootstrap.show_import_offer
                }
                onFinish={handleCompleteFinish}
              />
            </m.div>
          )}
        </AnimatePresence>
      </div>

      {step !== 'welcome' && step !== 'complete' && (
        <div className="onb-v2-float-footer">
          <MotionPress
            variant="ghost"
            haptic="light"
            className="onb-v2-float-back"
            onClick={goBack}
            disabled={saving}
            ariaLabel={t('redesign.onboardingV2.back')}
          >
            <Icon name="chevron-left" size={18} />
            {t('redesign.onboardingV2.back')}
          </MotionPress>
          <div className="onb-v2-float-ctas">
            {step === 'profile' && (
              <>
                <MotionPress
                  variant="ghost"
                  haptic="light"
                  className="onb-v2-float-ghost"
                  onClick={handleProfileSkip}
                  disabled={saving}
                >
                  {t('redesign.onboardingV2.profile.skip')}
                </MotionPress>
                <MotionPress
                  variant="primary"
                  haptic="medium"
                  className="onb-v2-float-cta"
                  onClick={handleProfileSubmit}
                  disabled={saving}
                >
                  {saving
                    ? t('redesign.onboardingV2.saving')
                    : t('redesign.onboardingV2.profile.cta')}
                </MotionPress>
              </>
            )}
            {step === 'genres' && (
              <MotionPress
                variant="primary"
                haptic="medium"
                className="onb-v2-float-cta"
                onClick={handleGenresSubmit}
                disabled={
                  saving ||
                  selectedGenres.length < MIN_GENRES
                }
              >
                {saving
                  ? t('redesign.onboardingV2.saving')
                  : t('redesign.onboardingV2.genres.cta')}
              </MotionPress>
            )}
            {step === 'swipe' && canFinish && (
              <MotionPress
                variant="primary"
                haptic="medium"
                className="onb-v2-float-cta"
                onClick={handleManualFinish}
                disabled={saving}
              >
                {t('redesign.onboardingV2.swipe.finish')}
              </MotionPress>
            )}
          </div>
        </div>
      )}

      {bootstrapErr && (
        <p
          className="onb-v2-name-error"
          role="alert"
          style={{ padding: '0 24px 16px' }}
        >
          {t('redesign.onboardingMsg.saveFail')}
        </p>
      )}

      <audio
        ref={audio.audioRef}
        preload="none"
        style={{ display: 'none' }}
      />
    </div>
  )
}

interface ProgressBarProps {
  steps: number
  currentIndex: number
}

function ProgressBar({
  steps,
  currentIndex,
}: ProgressBarProps) {
  return (
    <div
      className="onb-v2-progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={steps}
      aria-valuenow={Math.max(0, currentIndex + 1)}
    >
      {Array.from({ length: steps }, (_, i) => {
        const isDone = i < currentIndex
        const isCurrent = i === currentIndex
        const klass = [
          'onb-v2-progress__bar',
          isDone ? 'is-done' : '',
          isCurrent ? 'is-current' : '',
        ]
          .filter(Boolean)
          .join(' ')
        return <div key={i} className={klass} />
      })}
    </div>
  )
}

interface WelcomeStepProps {
  onStart: () => void
}

function WelcomeStep({ onStart }: WelcomeStepProps) {
  const { t } = useTranslation()
  return (
    <div className="onb-v2-welcome">
      <div
        className="onb-v2-welcome__logo"
        aria-hidden="true"
      >
        {t('redesign.onboardingV2.welcome.logo')}
      </div>
      <h1 className="onb-v2-welcome__title">
        {t('redesign.onboardingV2.welcome.title')}
      </h1>
      <p className="onb-v2-welcome__subtitle">
        {t(
          'redesign.onboardingV2.welcome.subtitle',
        )}
      </p>
      <div
        className="onb-v2-footer"
        style={{ width: '100%', maxWidth: 360 }}
      >
        <MotionPress
          variant="primary"
          haptic="medium"
          className="onb-v2-cta"
          onClick={onStart}
        >
          {t('redesign.onboardingV2.welcome.cta')}
        </MotionPress>
      </div>
    </div>
  )
}

interface ProfileStepProps {
  bootstrap: OnboardingBootstrap
  displayName: string
  onChangeName: (s: string) => void
  onUseDefaultAvatar: () => void
  onResetUseDefault: () => void
  err: string | null
}

function ProfileStep({
  bootstrap,
  displayName,
  onChangeName,
  onUseDefaultAvatar,
  onResetUseDefault,
  err,
}: ProfileStepProps) {
  const { t } = useTranslation()
  const defaults = bootstrap.profile_defaults
  return (
    <>
      <div className="onb-v2-step__hero">
        <h1 className="onb-v2-step__title">
          {t('redesign.onboardingV2.profile.title')}
        </h1>
        <p className="onb-v2-step__subtitle">
          {t(
            'redesign.onboardingV2.profile.subtitle',
          )}
        </p>
      </div>
      <div className="onb-v2-step__body">
        <div className="onb-v2-profile">
          <AvatarBuilder
            initials={defaults.suggested_initials}
            defaultUrl={
              defaults.suggested_avatar_url
            }
            hasCustomAvatar={defaults.has_custom_avatar}
            onUploaded={() => onResetUseDefault()}
            onResetToDefault={() =>
              onUseDefaultAvatar()
            }
          />
          <div className="onb-v2-name-field">
            <label
              htmlFor="onb-v2-name-input"
              className="onb-v2-name-field__label"
            >
              {t(
                'redesign.onboardingV2.profile.label',
              )}
            </label>
            <input
              id="onb-v2-name-input"
              type="text"
              className="onb-v2-name-input"
              maxLength={64}
              autoComplete="off"
              spellCheck={false}
              enterKeyHint="done"
              placeholder={t(
                'redesign.onboardingV2.profile.placeholder',
              )}
              value={displayName}
              onChange={(e) =>
                onChangeName(e.target.value)
              }
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.currentTarget.blur()
                }
              }}
            />
            <p
              className="onb-v2-name-error"
              aria-live="polite"
            >
              {err ?? '\u00A0'}
            </p>
          </div>
        </div>
      </div>
    </>
  )
}

interface GenresStepProps {
  bubbles: OnboardingBootstrap['genre_bubbles']
  selected: string[]
  onToggle: (g: string) => void
}

function GenresStep({
  bubbles,
  selected,
  onToggle,
}: GenresStepProps) {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')

  const genreAudioRef =
    useRef<HTMLAudioElement | null>(null)
  const playingGenreRef = useRef<string | null>(null)
  const timerRef = useRef<number | null>(null)
  const queuesRef = useRef(
    new Map<string, Track[]>(),
  )
  const idxRef = useRef(new Map<string, number>())
  const playNextRef = useRef<
    ((genre: string) => void) | null
  >(null)
  const bubblesRef = useRef(bubbles)

  const stopGenreAudio = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const a = genreAudioRef.current
    if (a) {
      a.pause()
      a.onended = null
      a.src = ''
    }
    playingGenreRef.current = null
  }, [])

  const playNext = useCallback(
    (genre: string) => {
      if (playingGenreRef.current !== genre) return
      const a = genreAudioRef.current
      if (!a) return
      const queue = queuesRef.current.get(genre)
      if (!queue || queue.length === 0) return

      let idx = idxRef.current.get(genre) ?? 0
      if (idx >= queue.length) {
        for (
          let i = queue.length - 1;
          i > 0;
          i--
        ) {
          const j = Math.floor(
            Math.random() * (i + 1),
          )
          ;[queue[i], queue[j]] = [
            queue[j],
            queue[i],
          ]
        }
        idx = 0
      }
      idxRef.current.set(genre, idx + 1)
      const track = queue[idx]

      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current)
      }
      a.pause()
      a.src = `/api/v1/track-preview/${track.id}/segment.mp4`
      a.muted = false
      a.onended = () => {
        if (timerRef.current !== null) {
          window.clearTimeout(timerRef.current)
          timerRef.current = null
        }
        playNextRef.current?.(genre)
      }
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null
        if (genreAudioRef.current) {
          genreAudioRef.current.pause()
          genreAudioRef.current.onended = null
        }
        playNextRef.current?.(genre)
      }, 15000)
      void a.play().catch(() => {
        if (playingGenreRef.current === genre) {
          stopGenreAudio()
        }
      })
    },
    [stopGenreAudio],
  )

  playNextRef.current = playNext

  const startGenrePreview = useCallback(
    async (genre: string) => {
      stopGenreAudio()
      playingGenreRef.current = genre
      const a = genreAudioRef.current
      if (!a) return

      // Always prime in user-gesture tick regardless of
      // queue cache. Without this, cached queues skip
      // priming and a.play() is blocked by autoplay policy.
      a.muted = true
      a.src = GENRE_SILENT_WAV
      void a.play().catch(() => {})

      let queue = queuesRef.current.get(genre)

      if (!queue) {

        try {
          const resp: OnboardingGenrePreviewResponse =
            await api.fetchGenrePreviewQueue(
              genre,
              10,
            )
          if (playingGenreRef.current !== genre) {
            return
          }
          const arr = [...resp.items]
          for (
            let i = arr.length - 1;
            i > 0;
            i--
          ) {
            const j = Math.floor(
              Math.random() * (i + 1),
            )
            ;[arr[i], arr[j]] = [arr[j], arr[i]]
          }
          queue = arr
          queuesRef.current.set(genre, queue)
          idxRef.current.set(genre, 0)
        } catch {
          if (playingGenreRef.current === genre) {
            playingGenreRef.current = null
          }
          a.muted = false
          return
        }
      }

      if (!queue || queue.length === 0) {
        if (playingGenreRef.current === genre) {
          playingGenreRef.current = null
        }
        return
      }
      if (playingGenreRef.current !== genre) return
      playNext(genre)
    },
    [stopGenreAudio, playNext],
  )

  // Pre-fetch queues for visible genres on mount
  // so the first tap on each genre is synchronous.
  useEffect(() => {
    let active = true
    const prefetch = async () => {
      for (const b of bubblesRef.current.slice(
        0,
        14,
      )) {
        if (!active) return
        if (queuesRef.current.has(b.genre)) continue
        try {
          const resp =
            await api.fetchGenrePreviewQueue(
              b.genre,
              5,
            )
          if (!active) return
          const arr = [...resp.items]
          for (
            let i = arr.length - 1;
            i > 0;
            i--
          ) {
            const j = Math.floor(
              Math.random() * (i + 1),
            )
            ;[arr[i], arr[j]] = [arr[j], arr[i]]
          }
          queuesRef.current.set(b.genre, arr)
          idxRef.current.set(b.genre, 0)
        } catch {}
      }
    }
    void prefetch()
    return () => {
      active = false
    }
  }, [])

  const handleToggle = useCallback(
    (genre: string) => {
      const wasSelected = selected.includes(genre)
      onToggle(genre)
      if (!wasSelected) {
        void startGenrePreview(genre)
      } else if (
        playingGenreRef.current === genre
      ) {
        stopGenreAudio()
      }
    },
    [selected, onToggle, startGenrePreview, stopGenreAudio],
  )

  useEffect(() => {
    return () => {
      stopGenreAudio()
    }
  }, [stopGenreAudio])

  const filteredBubbles = useMemo(() => {
    if (!searchQuery.trim()) return bubbles
    const q = searchQuery.toLowerCase()
    return bubbles.filter((b) =>
      b.genre.toLowerCase().includes(q),
    )
  }, [bubbles, searchQuery])

  const remaining = Math.max(
    0,
    MIN_GENRES - selected.length,
  )
  const counterText =
    remaining > 0
      ? t(
          'redesign.onboardingV2.genres.counterMore',
          { count: remaining },
        )
      : t(
          'redesign.onboardingV2.genres.counterDone',
          { count: selected.length },
        )

  return (
    <>
      <div className="onb-v2-step__hero">
        <h1 className="onb-v2-step__title">
          {t('redesign.onboardingV2.genres.title')}
        </h1>
        <p className="onb-v2-step__subtitle">
          {t(
            'redesign.onboardingV2.genres.subtitle',
            { min: MIN_GENRES },
          )}
        </p>
      </div>
      <div className="onb-v2-step__body">
        <div className="onb-v2-genre-search">
          <Icon name="search" size={15} />
          <input
            className="onb-v2-genre-search__input"
            type="search"
            enterKeyHint="search"
            placeholder={t(
              'redesign.onboardingV2.genres.searchPlaceholder',
            )}
            value={searchQuery}
            onChange={(e) =>
              setSearchQuery(e.target.value)
            }
          />
          {searchQuery && (
            <button
              type="button"
              className="onb-v2-genre-search__clear"
              onClick={() => setSearchQuery('')}
              aria-label="Clear"
            >
              <Icon name="x" size={14} />
            </button>
          )}
        </div>
        {filteredBubbles.length > 0 ? (
          <div className="onb-v2-bubbles">
            {filteredBubbles.map((b) => (
              <GenreBubble
                key={b.genre}
                bubble={b}
                selected={selected.includes(
                  b.genre,
                )}
                onToggle={handleToggle}
              />
            ))}
          </div>
        ) : (
          <p className="onb-v2-step__subtitle">
            {searchQuery
              ? t(
                  'redesign.onboardingV2.genres.searchEmpty',
                )
              : t(
                  'redesign.onboardingV2.genres.empty',
                )}
          </p>
        )}
        <p className="onb-v2-counter">
          {counterText}
        </p>
      </div>
      <audio
        ref={genreAudioRef}
        preload="none"
        style={{ display: 'none' }}
      />
    </>
  )
}

interface SwipeStepProps {
  tracks: Track[]
  index: number
  loading: boolean
  playingId: number | null
  audioBlocked: boolean
  onLike: () => void
  onDislike: () => void
  onSkipCard: () => void
  onTogglePreview: () => void
  reduce: boolean
}

function SwipeStep({
  tracks,
  index,
  loading,
  playingId,
  audioBlocked,
  onLike,
  onDislike,
  onSkipCard,
  onTogglePreview,
  reduce,
}: SwipeStepProps) {
  const { t } = useTranslation()
  const top = tracks[index]
  const next = tracks[index + 1]

  return (
    <>
      <div className="onb-v2-step__hero">
        <h1 className="onb-v2-step__title">
          {t('redesign.onboardingV2.swipe.title')}
        </h1>
        <p className="onb-v2-step__subtitle">
          {t(
            'redesign.onboardingV2.swipe.subtitle',
          )}
        </p>
      </div>
      <div className="onb-v2-swipe">
        <div className="onb-v2-swipe-stack">
          {loading && tracks.length === 0 && (
            <div className="onb-v2-swipe-empty">
              {t(
                'redesign.onboardingV2.swipe.loading',
              )}
            </div>
          )}
          {!loading && tracks.length === 0 && (
            <div className="onb-v2-swipe-empty">
              {t(
                'redesign.onboardingV2.swipe.empty',
              )}
            </div>
          )}
          {next && !reduce && (
            <SwipeBackdropCard
              key={`bg-${next.id}`}
              track={next}
            />
          )}
          {top && (
            <SwipeCard
              key={top.id}
              track={top}
              isPlaying={playingId === top.id}
              audioBlocked={audioBlocked}
              onLike={onLike}
              onDislike={onDislike}
              onTogglePreview={onTogglePreview}
              reduce={reduce}
            />
          )}
          {!top && loading && (
            <div className="onb-v2-swipe-empty">
              {t(
                'redesign.onboardingV2.swipe.loading',
              )}
            </div>
          )}
        </div>
        <p
          className="onb-v2-counter"
          style={{ marginTop: 12 }}
        >
          {tracks.length > 0
            ? t(
                'redesign.onboardingV2.swipe.counter',
                {
                  current: Math.min(
                    index + 1,
                    tracks.length,
                  ),
                  total: tracks.length,
                },
              )
            : '\u00A0'}
        </p>
        {top && (
          <div className="onb-v2-swipe-actions">
            <MotionPress
              variant="ghost"
              haptic="medium"
              className="onb-v2-swipe-btn onb-v2-swipe-btn--dislike"
              onClick={onDislike}
              ariaLabel={t(
                'redesign.onboardingV2.swipe.dislike',
              )}
            >
              <Icon name="x" size={26} />
            </MotionPress>
            <MotionPress
              variant="ghost"
              haptic="light"
              className="onb-v2-swipe-btn onb-v2-swipe-btn--skip"
              onClick={onSkipCard}
              ariaLabel={t(
                'redesign.onboardingV2.swipe.skipCard',
              )}
            >
              <Icon name="chevron-right" size={26} />
            </MotionPress>
            <MotionPress
              variant="ghost"
              haptic="medium"
              className="onb-v2-swipe-btn onb-v2-swipe-btn--like"
              onClick={onLike}
              ariaLabel={t(
                'redesign.onboardingV2.swipe.like',
              )}
            >
              <Icon name="heart" size={26} />
            </MotionPress>
          </div>
        )}
      </div>
    </>
  )
}

interface SwipeBackdropCardProps {
  track: Track
}

function SwipeBackdropCard({
  track,
}: SwipeBackdropCardProps) {
  return (
    <div
      className="onb-v2-swipe-card onb-v2-swipe-card--backdrop"
      aria-hidden="true"
    >
      <CoverArt track={track} />
    </div>
  )
}

interface SwipeCardProps {
  track: Track
  isPlaying: boolean
  audioBlocked: boolean
  onLike: () => void
  onDislike: () => void
  onTogglePreview: () => void
  reduce: boolean
}

function SwipeCard({
  track,
  isPlaying,
  audioBlocked,
  onLike,
  onDislike,
  onTogglePreview,
  reduce,
}: SwipeCardProps) {
  const { t } = useTranslation()
  const x = useMotionValue(0)
  const rotate = useTransform(
    x,
    [-200, 0, 200],
    [-12, 0, 12],
  )
  const likeOpacity = useTransform(
    x,
    [40, SWIPE_THRESHOLD],
    [0, 1],
  )
  const nopeOpacity = useTransform(
    x,
    [-SWIPE_THRESHOLD, -40],
    [1, 0],
  )

  const handleDragEnd = (
    _: unknown,
    info: PanInfo,
  ) => {
    const v = info.offset.x
    if (v > SWIPE_THRESHOLD) {
      onLike()
    } else if (v < -SWIPE_THRESHOLD) {
      onDislike()
    }
  }

  if (reduce) {
    return (
      <div
        className="onb-v2-swipe-card"
        onClick={onTogglePreview}
        role="button"
        tabIndex={0}
      >
        <CoverArt
          track={track}
          isPlaying={isPlaying}
        />
        <CardInfo track={track} />
        {audioBlocked && <MuteHint />}
      </div>
    )
  }

  return (
    <m.div
      className="onb-v2-swipe-card"
      drag="x"
      dragConstraints={{
        left: -240,
        right: 240,
      }}
      dragElastic={0.6}
      style={{ x, rotate }}
      onDragEnd={handleDragEnd}
      onTap={onTogglePreview}
      whileTap={{ cursor: 'grabbing' }}
      transition={SPRING_SNAPPY}
      exit={{
        opacity: 0,
        scale: 0.95,
        transition: TWEEN_FAST,
      }}
    >
      <CoverArt
        track={track}
        isPlaying={isPlaying}
      />
      <CardInfo track={track} />
      <m.span
        className="onb-v2-swipe-card__badge onb-v2-swipe-card__badge--like"
        style={{ opacity: likeOpacity }}
        aria-hidden="true"
      >
        {t('redesign.onboardingV2.swipe.badgeLike')}
      </m.span>
      <m.span
        className="onb-v2-swipe-card__badge onb-v2-swipe-card__badge--dislike"
        style={{ opacity: nopeOpacity }}
        aria-hidden="true"
      >
        {t('redesign.onboardingV2.swipe.badgeNope')}
      </m.span>
      {audioBlocked && <MuteHint />}
    </m.div>
  )
}

function MuteHint() {
  const { t } = useTranslation()
  return (
    <span
      className="onb-v2-swipe-card__mute-hint"
      role="status"
    >
      <Icon name="volume-off" size={16} />
      {t('redesign.onboardingV2.swipe.tapToUnmute')}
    </span>
  )
}

interface CardArtProps {
  track: Track
  isPlaying?: boolean
}

function CoverArt({
  track,
  isPlaying = false,
}: CardArtProps) {
  return (
    <div className="onb-v2-swipe-card__cover">
      <CoverImage
        coverKey={track.cover_key}
        size={360}
      />
      <span className="onb-v2-swipe-card__cover-fade" />
      <span
        className={[
          'onb-v2-swipe-card__play-pulse',
          isPlaying ? 'is-playing' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        aria-hidden="true"
      >
        <Icon
          name={isPlaying ? 'pause' : 'play'}
          size={28}
        />
      </span>
    </div>
  )
}

function CardInfo({
  track,
}: {
  track: Track
}) {
  return (
    <div className="onb-v2-swipe-card__info">
      <h3 className="onb-v2-swipe-card__title">
        {track.title}
      </h3>
      <p className="onb-v2-swipe-card__artist">
        {track.artist || '\u00A0'}
      </p>
    </div>
  )
}

interface CompleteStepProps {
  showImport: boolean
  onFinish: (openImport: boolean) => void
}

function CompleteStep({
  showImport,
  onFinish,
}: CompleteStepProps) {
  const { t } = useTranslation()
  return (
    <div className="onb-v2-complete">
      <div
        className="onb-v2-complete__check"
        aria-hidden="true"
      >
        <Icon name="check" size={40} />
      </div>
      <h1 className="onb-v2-complete__title">
        {t('redesign.onboardingV2.complete.title')}
      </h1>
      <p className="onb-v2-complete__subtitle">
        {t(
          'redesign.onboardingV2.complete.subtitle',
        )}
      </p>
      {showImport && (
        <button
          type="button"
          className="onb-v2-complete__import-card"
          onClick={() => onFinish(true)}
        >
          <span className="onb-v2-complete__import-icon">
            <Icon name="download" size={20} />
          </span>
          <span className="onb-v2-complete__import-text">
            <span className="onb-v2-complete__import-title">
              {t(
                'redesign.onboardingV2.complete.importTitle',
              )}
            </span>
            <span className="onb-v2-complete__import-hint">
              {t(
                'redesign.onboardingV2.complete.importHint',
              )}
            </span>
          </span>
          <Icon name="chevron-right" size={18} />
        </button>
      )}
      <div
        className="onb-v2-footer"
        style={{ width: '100%', maxWidth: 360 }}
      >
        <MotionPress
          variant="primary"
          haptic="medium"
          className="onb-v2-cta"
          onClick={() => onFinish(false)}
        >
          {t('redesign.onboardingV2.complete.cta')}
        </MotionPress>
      </div>
    </div>
  )
}
