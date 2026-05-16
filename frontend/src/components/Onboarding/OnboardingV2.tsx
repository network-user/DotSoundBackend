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
  type ValueAnimationTransition,
  animate,
  useDragControls,
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
import { getIsAdmin, hapticSelection } from '@/lib/telegram'
import { useOnboardingAudio } from '@/hooks/useOnboardingAudio'
import { AvatarBuilder } from '@/components/Onboarding/AvatarBuilder'
import { GenreBubble } from '@/components/Onboarding/GenreBubble'
import { useBrandLabel } from '@/lib/brand'
import { LEGAL_VERSION } from '@/views/legalContent'
import type {
  ArtistInfo,
  OnboardingArtistItem,
  OnboardingBootstrap,
  OnboardingTasteDecision,
  Track,
} from '@/types/api'

const ARTIST_SEARCH_MIN_LEN = 2
const ARTIST_SEARCH_DEBOUNCE_MS = 320

import '@/styles/onboarding.css'

interface Props {
  onComplete: () => void
}

type Step =
  | 'welcome'
  | 'profile'
  | 'genres'
  | 'artists'
  | 'swipe'
  | 'complete'

interface SwipeDecisionOptions {
  haptic?: boolean
}

const MIN_GENRES = 3
const SWIPE_BATCH = 5
const SWIPE_THRESHOLD = 110
const SWIPE_VELOCITY_THRESHOLD = 720
const SWIPE_VELOCITY_MIN_OFFSET = 36

const STEP_ORDER: Step[] = [
  'welcome',
  'profile',
  'genres',
  'artists',
  'swipe',
  'complete',
]

const PROGRESS_STEPS: Step[] = [
  'profile',
  'genres',
  'artists',
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

  const [selectedArtistIds, setSelectedArtistIds] = useState<
    number[]
  >([])
  const [onboardingArtists, setOnboardingArtists] = useState<
    OnboardingArtistItem[]
  >([])
  const [artistsLoading, setArtistsLoading] = useState(false)

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
  const [tasteExhausted, setTasteExhausted] = useState(false)

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
    if (step !== 'artists') return
    let cancelled = false
    setArtistsLoading(true)
    api
      .getOnboardingArtists(selectedGenres)
      .then((artists) => {
        if (cancelled) return
        setOnboardingArtists(artists)
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setArtistsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [step, selectedGenres])

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
        setTasteExhausted(false)
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
      setTasteExhausted(false)
      lastFetchCountRef.current = 0
      autoPlayedTrackRef.current = null
    }
    setStep(STEP_ORDER[i - 1])
  }, [step, audio])

  const handleWelcomeStart = () => {
    if (bootstrapErr) return
    hapticSelection()
    audio.prime()
    goNext('welcome')
  }

  // TEMPORARY: admin escape hatch for fresh deploys where there
  // are no tracks yet, so the swipe step cannot be completed.
  // Remove once the catalog has enough content for any user to
  // finish onboarding on their own.
  const isAdmin = useMemo(() => getIsAdmin(), [])
  const handleAdminSkip = useCallback(async () => {
    if (saving) return
    setSaving(true)
    try {
      await api.smartSkipOnboarding()
      onComplete()
    } catch {
      setSaving(false)
    }
  }, [saving, onComplete])

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

  const handleGenresSubmit = () => {
    if (saving || selectedGenres.length < MIN_GENRES) return
    audio.prime()
    hapticSelection()
    goNext('genres')
  }

  const toggleArtist = (id: number) => {
    hapticSelection()
    setSelectedArtistIds((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : [...prev, id],
    )
  }

  const handleArtistsSubmit = async () => {
    if (saving) return
    audio.prime()
    setSaving(true)
    try {
      await api.saveOnboardingPreferences({
        genres: selectedGenres,
        artist_ids: selectedArtistIds,
        moods: [],
      })
      trackActivationEvent('onboarding_step_complete', {
        meta: {
          step: 'artists',
          count: selectedArtistIds.length,
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
      goNext('artists')
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
    (
      decision: OnboardingTasteDecision,
      options?: SwipeDecisionOptions,
    ) => {
      const tr = tasteTracks[tasteIndex]
      if (!tr) return
      if (options?.haptic !== false) {
        hapticSelection()
      }
      setTasteDecisions((prev) => [
        ...prev,
        { track_id: tr.id, decision },
      ])
      setTasteIndex((i) => i + 1)
    },
    [tasteTracks, tasteIndex],
  )

  const togglePreview = useCallback(() => {
    const tr = tasteTracks[tasteIndex]
    if (!tr) return
    if (
      audio.state === 'playing' ||
      (audio.state === 'paused' &&
        audio.currentTrackId === tr.id)
    ) {
      audio.toggle({ step: 'swipe' })
      return
    }
    audio.prime()
    audio.playTrack(
      tr.id,
      `/api/v1/tracks/${tr.id}/audio?force_progressive=true`,
      { step: 'swipe' },
    )
  }, [audio, tasteTracks, tasteIndex])

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
    if (tasteExhausted) return
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
          setTasteExhausted(false)
        } else {
          setTasteExhausted(true)
        }
      })
      .catch(() => {
        if (!cancelled) setTasteExhausted(true)
      })
      .finally(() => {
        if (!cancelled) setTasteLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [step, tasteIndex, tasteTracks, tasteExhausted])

  useEffect(() => {
    if (!tasteExhausted) return
    if (step !== 'swipe') return
    audio.stop()
  }, [tasteExhausted, step, audio])

  useEffect(() => {
    if (step !== 'swipe') return
    const tr = tasteTracks[tasteIndex]
    if (!tr) return
    if (autoPlayedTrackRef.current === tr.id) return
    autoPlayedTrackRef.current = tr.id
    audio.playTrack(
      tr.id,
      `/api/v1/tracks/${tr.id}/audio?force_progressive=true`,
      { step: 'swipe' },
    )
  }, [step, tasteIndex, tasteTracks, audio])

  const canFinish =
    tasteDecisions.length >= SWIPE_BATCH || tasteExhausted

  const handleManualFinish = useCallback(() => {
    hapticSelection()
    void finalizeSwipe(tasteDecisions)
  }, [tasteDecisions, finalizeSwipe])

  const handleCompleteFinish = useCallback(
    (openImport: boolean) => {
      hapticSelection()
      if (openImport) {
        try {
          window.localStorage.setItem(
            'ds_pending_import_open',
            '1',
          )
        } catch {
          /* ignore */
        }
      }
      onComplete()
    },
    [onComplete],
  )

  const progressIndex = useMemo(() => {
    if (step === 'complete') return PROGRESS_STEPS.length
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
                onAdminSkip={
                  isAdmin ? handleAdminSkip : null
                }
                adminSkipBusy={saving}
              />
            </m.div>
          )}

          {step === 'profile' && bootstrap && (
            <m.div
              key="profile"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={TWEEN_FAST}
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
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={TWEEN_FAST}
              className="onb-v2-step"
            >
              <GenresStep
                bubbles={bootstrap.genre_bubbles}
                selected={selectedGenres}
                onToggle={toggleGenre}
              />
            </m.div>
          )}

          {step === 'artists' && (
            <m.div
              key="artists"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={TWEEN_FAST}
              className="onb-v2-step"
            >
              <ArtistsStep
                artists={onboardingArtists}
                selected={selectedArtistIds}
                onToggle={toggleArtist}
                loading={artistsLoading}
              />
            </m.div>
          )}

          {step === 'swipe' && (
            <m.div
              key="swipe"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={TWEEN_FAST}
              className="onb-v2-step"
            >
              <SwipeStep
                tracks={tasteTracks}
                index={tasteIndex}
                loading={tasteLoading}
                exhausted={tasteExhausted}
                playingId={
                  audio.state === 'playing'
                    ? audio.currentTrackId
                    : null
                }
                audioLoading={audio.state === 'loading'}
                audioBlocked={
                  audio.state === 'blocked' ||
                  audio.state === 'error'
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
              <>
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
                    : t(
                        'redesign.onboardingV2.genres.cta',
                      )}
                </MotionPress>
                {selectedGenres.length < MIN_GENRES && (
                  <p className="onb-v2-genres-hint">
                    {t(
                      'redesign.onboardingV2.genres.counterMore',
                      {
                        count:
                          MIN_GENRES -
                          selectedGenres.length,
                      },
                    )}
                  </p>
                )}
              </>
            )}
            {step === 'artists' && (
              <MotionPress
                variant="primary"
                haptic="medium"
                className="onb-v2-float-cta"
                onClick={handleArtistsSubmit}
                disabled={saving}
              >
                {saving
                  ? t('redesign.onboardingV2.saving')
                  : t('onboarding.artists.cta')}
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
        preload="auto"
        playsInline
        crossOrigin="anonymous"
        aria-hidden
        tabIndex={-1}
        className="onb-v2-hidden-audio"
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
  onAdminSkip: (() => void) | null
  adminSkipBusy: boolean
}

function WelcomeStep({
  onStart,
  onAdminSkip,
  adminSkipBusy,
}: WelcomeStepProps) {
  const { t } = useTranslation()
  const brand = useBrandLabel()
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
      <blockquote className="onb-v2-welcome__quote">
        {t('redesign.onboardingV2.welcome.quote', {
          brand,
        })}
      </blockquote>
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
        {onAdminSkip && (
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="onb-v2-admin-skip"
            onClick={onAdminSkip}
            disabled={adminSkipBusy}
            ariaLabel="Пропустить онбординг (admin)"
            style={{
              marginTop: 12,
              opacity: 0.7,
              fontSize: 13,
            }}
          >
            {adminSkipBusy
              ? '…'
              : 'Пропустить онбординг (admin)'}
          </MotionPress>
        )}
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
              aria-label={t('onboarding.searchClear')}
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
                onToggle={onToggle}
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
    </>
  )
}

interface SwipeStepProps {
  tracks: Track[]
  index: number
  loading: boolean
  exhausted: boolean
  playingId: number | null
  audioLoading: boolean
  audioBlocked: boolean
  onLike: (options?: SwipeDecisionOptions) => void
  onDislike: (options?: SwipeDecisionOptions) => void
  onSkipCard: () => void
  onTogglePreview: () => void
  reduce: boolean
}

function SwipeStep({
  tracks,
  index,
  loading,
  exhausted,
  playingId,
  audioLoading,
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
  const [exitDir, setExitDir] = useState<-1 | 0 | 1>(0)

  // Preload next 2 tracks' audio so the auto-play swap on swipe is
  // instant instead of waiting for transcode each time.
  useEffect(() => {
    const upcoming = tracks.slice(index + 1, index + 3)
    const els: HTMLAudioElement[] = []
    for (const t of upcoming) {
      try {
        const a = new Audio()
        a.preload = 'auto'
        a.src = `/api/v1/tracks/${t.id}/audio?force_progressive=true`
        a.load()
        els.push(a)
      } catch {
        /* ignore */
      }
    }
    return () => {
      for (const a of els) {
        try {
          a.src = ''
        } catch {
          /* ignore */
        }
      }
    }
  }, [tracks, index])

  const handleLike = useCallback(
    (options?: SwipeDecisionOptions) => {
      setExitDir(1)
      onLike(options)
    },
    [onLike],
  )

  const handleDislike = useCallback(
    (options?: SwipeDecisionOptions) => {
      setExitDir(-1)
      onDislike(options)
    },
    [onDislike],
  )

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
            <div className="onb-v2-swipe-loading">
              <div className="upload-spinner" />
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
          <AnimatePresence custom={exitDir} initial={false}>
            {top && (
              <SwipeCard
                key={top.id}
                track={top}
                isPlaying={playingId === top.id}
                audioLoading={audioLoading}
                audioBlocked={audioBlocked}
                onLike={handleLike}
                onDislike={handleDislike}
                onTogglePreview={onTogglePreview}
                reduce={reduce}
              />
            )}
          </AnimatePresence>
          {!top &&
            exhausted &&
            !loading &&
            tracks.length > 0 && (
              <div className="onb-v2-swipe-all-done">
                <p className="onb-v2-swipe-all-done__text">
                  {t(
                    'redesign.onboardingV2.swipe.allDoneHint',
                  )}
                </p>
              </div>
            )}
          {!top && loading && (
            <div className="onb-v2-swipe-loading">
              <div className="upload-spinner" />
            </div>
          )}
        </div>
        <p
          className="onb-v2-counter"
          style={{ marginTop: 12 }}
        >
          {exhausted && !top
            ? '\u00A0'
            : tracks.length > 0
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
              onClick={() => handleDislike()}
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
              onClick={() => handleLike()}
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
  audioLoading: boolean
  audioBlocked: boolean
  onLike: (options?: SwipeDecisionOptions) => void
  onDislike: (options?: SwipeDecisionOptions) => void
  onTogglePreview: () => void
  reduce: boolean
}

function SwipeCard({
  track,
  isPlaying,
  audioLoading,
  audioBlocked,
  onLike,
  onDislike,
  onTogglePreview,
  reduce,
}: SwipeCardProps) {
  const { t } = useTranslation()
  const [transportVisible, setTransportVisible] = useState(true)
  const transportHideTimerRef = useRef<ReturnType<
    typeof setTimeout
  > | null>(null)
  const committedRef = useRef(false)

  useEffect(() => {
    if (transportHideTimerRef.current) {
      clearTimeout(transportHideTimerRef.current)
      transportHideTimerRef.current = null
    }
    if (!isPlaying) {
      setTransportVisible(true)
      return
    }
    if (audioLoading) {
      setTransportVisible(true)
      return
    }
    setTransportVisible(true)
    transportHideTimerRef.current = setTimeout(() => {
      setTransportVisible(false)
      transportHideTimerRef.current = null
    }, 2200)
    return () => {
      if (transportHideTimerRef.current) {
        clearTimeout(transportHideTimerRef.current)
        transportHideTimerRef.current = null
      }
    }
  }, [isPlaying, audioLoading, track.id])

  const x = useMotionValue(0)
  const dragControls = useDragControls()
  const xSpan = reduce ? 120 : 200
  const rotate = useTransform(
    x,
    [-xSpan, 0, xSpan],
    reduce ? [-7, 0, 7] : [-12, 0, 12],
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
  const likeTint = useTransform(
    x,
    [0, SWIPE_THRESHOLD * 1.5],
    [0, 0.55],
  )
  const nopeTint = useTransform(
    x,
    [-SWIPE_THRESHOLD * 1.5, 0],
    [0.55, 0],
  )

  const resolveSwipeDirection = useCallback(
    (offsetX: number, velocityX: number): -1 | 0 | 1 => {
      if (offsetX > SWIPE_THRESHOLD) return 1
      if (offsetX < -SWIPE_THRESHOLD) return -1
      if (
        velocityX > SWIPE_VELOCITY_THRESHOLD &&
        offsetX > SWIPE_VELOCITY_MIN_OFFSET
      ) {
        return 1
      }
      if (
        velocityX < -SWIPE_VELOCITY_THRESHOLD &&
        offsetX < -SWIPE_VELOCITY_MIN_OFFSET
      ) {
        return -1
      }
      return 0
    },
    [],
  )

  const commitSwipe = useCallback(
    (dir: -1 | 1) => {
      if (committedRef.current) return
      committedRef.current = true
      hapticSelection()

      const exitX = dir * (reduce ? 340 : 560)
      const controls = animate(
        x,
        exitX,
        {
          duration: reduce ? 0.18 : 0.24,
          ease: [0.2, 0.65, 0.3, 1],
        } as ValueAnimationTransition<number>,
      )
      void controls.then(() => {
        if (dir > 0) {
          onLike({ haptic: false })
          return
        }
        onDislike({ haptic: false })
      })
    },
    [onDislike, onLike, reduce, x],
  )

  const handleDragEnd = useCallback(
    (_: unknown, info: PanInfo) => {
      if (committedRef.current) return
      const dir = resolveSwipeDirection(
        info.offset.x,
        info.velocity.x,
      )
      if (dir !== 0) {
        commitSwipe(dir)
        return
      }
      void animate(
        x,
        0,
        SPRING_SNAPPY as ValueAnimationTransition<number>,
      )
    },
    [commitSwipe, resolveSwipeDirection, x],
  )

  useEffect(() => {
    committedRef.current = false
    x.set(0)
  }, [track.id, x])

  const startDrag = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (committedRef.current) return
      if (event.button !== 0) return
      dragControls.start(event)
    },
    [dragControls],
  )

  const handleTap = useCallback(() => {
    if (committedRef.current) return
    if (!onTogglePreview) return
    if (audioLoading) return
    if (isPlaying && !transportVisible) {
      onTogglePreview()
    }
  }, [
    audioLoading,
    isPlaying,
    onTogglePreview,
    transportVisible,
  ])

  return (
    <m.div
      className="onb-v2-swipe-card"
      drag="x"
      dragControls={dragControls}
      dragDirectionLock
      dragListener={false}
      dragConstraints={{
        left: -240,
        right: 240,
      }}
      dragElastic={reduce ? 0.35 : 0.6}
      dragMomentum={false}
      dragSnapToOrigin={false}
      style={{ x, rotate }}
      onPointerDownCapture={startDrag}
      onDragEnd={handleDragEnd}
      onTap={handleTap}
      whileTap={{ cursor: 'grabbing' }}
      transition={SPRING_SNAPPY}
      variants={{
        exit: (dir: number) => ({
          x: (dir || 0) * (reduce ? 300 : 520),
          rotate: (dir || 0) * (reduce ? 12 : 22),
          opacity: 0,
          transition: {
            duration: reduce ? 0.18 : 0.26,
            ease: [0.2, 0.65, 0.3, 1],
          },
        }),
      }}
      exit="exit"
    >
      <CoverArt
        track={track}
        isPlaying={isPlaying}
        isLoading={audioLoading}
        transportVisible={transportVisible}
        onTogglePreview={onTogglePreview}
      />
      <m.span
        className="onb-v2-swipe-card__tint onb-v2-swipe-card__tint--like"
        style={{ opacity: likeTint }}
        aria-hidden="true"
      />
      <m.span
        className="onb-v2-swipe-card__tint onb-v2-swipe-card__tint--nope"
        style={{ opacity: nopeTint }}
        aria-hidden="true"
      />
      <CardInfo track={track} />
      <m.span
        className="onb-v2-swipe-card__stamp onb-v2-swipe-card__stamp--like"
        style={{ opacity: likeOpacity }}
        aria-hidden="true"
      >
        <Icon name="heart" size={28} />
        <span className="onb-v2-swipe-card__stamp-text">
          {t('redesign.onboardingV2.swipe.badgeLike')}
        </span>
      </m.span>
      <m.span
        className="onb-v2-swipe-card__stamp onb-v2-swipe-card__stamp--nope"
        style={{ opacity: nopeOpacity }}
        aria-hidden="true"
      >
        <Icon name="x" size={28} />
        <span className="onb-v2-swipe-card__stamp-text">
          {t('redesign.onboardingV2.swipe.badgeNope')}
        </span>
      </m.span>
      {audioBlocked && !audioLoading && <MuteHint />}
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
  isLoading?: boolean
  transportVisible?: boolean
  onTogglePreview?: () => void
}

function CoverArt({
  track,
  isPlaying = false,
  isLoading = false,
  transportVisible = true,
  onTogglePreview,
}: CardArtProps) {
  const { t } = useTranslation()
  const interactive = typeof onTogglePreview === 'function'
  const showChrome =
    !interactive ||
    isLoading ||
    !isPlaying ||
    transportVisible
  const klass = [
    'onb-v2-swipe-card__play-pulse',
    isPlaying ? 'is-playing' : '',
    isLoading ? 'is-loading' : '',
    interactive ? 'is-interactive' : '',
  ]
    .filter(Boolean)
    .join(' ')
  const content = isLoading ? (
    <span className="onb-v2-swipe-card__spinner" />
  ) : (
    <Icon name={isPlaying ? 'pause' : 'play'} size={28} />
  )
  return (
    <div className="onb-v2-swipe-card__cover">
      <CoverImage
        coverKey={track.cover_key}
        size={360}
      />
      <span className="onb-v2-swipe-card__cover-fade" />
      {showChrome ? (
        interactive ? (
          <button
            type="button"
            className={klass}
            aria-label={
              isPlaying
                ? t('onboarding.preview.stop')
                : t('onboarding.preview.play')
            }
            onPointerDown={(e) => {
              e.stopPropagation()
            }}
            onClick={(e) => {
              e.stopPropagation()
              onTogglePreview?.()
            }}
          >
            {content}
          </button>
        ) : (
          <span className={klass} aria-hidden="true">
            {content}
          </span>
        )
      ) : null}
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
  const [accepting, setAccepting] = useState(false)

  const handleFinish = useCallback(
    async (openImport: boolean) => {
      if (accepting) return
      setAccepting(true)
      try {
        await api.completeOnboarding(LEGAL_VERSION)
      } catch {
        // Acceptance — best effort. Если запись провалилась,
        // онбординг всё равно завершён (onboarding_completed
        // уже выставлен ранее в finalizeSwipe). При следующем
        // входе toast о новой версии договора предложит
        // принять её повторно.
      }
      onFinish(openImport)
    },
    [accepting, onFinish],
  )

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
          onClick={() => {
            void handleFinish(true)
          }}
          disabled={accepting}
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
          onClick={() => {
            void handleFinish(false)
          }}
        >
          {t('redesign.onboardingV2.complete.cta')}
        </MotionPress>
        <p className="onb-v2-complete__legal-disclosure">
          Нажимая «
          {t('redesign.onboardingV2.complete.cta')}
          », вы подтверждаете, что вам исполнилось 18 лет,
          и принимаете{' '}
          <a
            href={`${import.meta.env.BASE_URL}legal/terms`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Условия использования
          </a>
          {' и '}
          <a
            href={`${import.meta.env.BASE_URL}legal/privacy`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Политику конфиденциальности
          </a>
          .
        </p>
      </div>
    </div>
  )
}

interface ArtistsStepProps {
  artists: OnboardingArtistItem[]
  selected: number[]
  onToggle: (id: number) => void
  loading: boolean
}

function toOnboardingArtistItem(
  artist: Pick<ArtistInfo, 'id' | 'name' | 'image_key'>,
): OnboardingArtistItem {
  return {
    id: artist.id,
    name: artist.name,
    image_key: artist.image_key,
  }
}

function ArtistsStep({
  artists,
  selected,
  onToggle,
  loading,
}: ArtistsStepProps) {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<
    OnboardingArtistItem[]
  >([])
  const [searchLoading, setSearchLoading] = useState(false)

  useEffect(() => {
    const q = searchQuery.trim()
    if (q.length < ARTIST_SEARCH_MIN_LEN) {
      setSearchResults([])
      setSearchLoading(false)
      return
    }

    let cancelled = false
    const timer = window.setTimeout(() => {
      setSearchLoading(true)
      api
        .getArtists(q, 40)
        .then((res) => {
          if (cancelled) return
          setSearchResults(
            res.items.map((item) => toOnboardingArtistItem(item)),
          )
        })
        .catch(() => {
          if (cancelled) return
          setSearchResults([])
        })
        .finally(() => {
          if (!cancelled) setSearchLoading(false)
        })
    }, ARTIST_SEARCH_DEBOUNCE_MS)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [searchQuery])

  const displayedArtists = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (q.length >= ARTIST_SEARCH_MIN_LEN) {
      const byId = new Map<number, OnboardingArtistItem>()
      for (const artist of artists) {
        if (selected.includes(artist.id)) {
          byId.set(artist.id, artist)
        }
      }
      for (const artist of searchResults) {
        byId.set(artist.id, artist)
      }
      return Array.from(byId.values())
    }
    if (!q) return artists
    return artists.filter((artist) =>
      artist.name.toLowerCase().includes(q),
    )
  }, [artists, searchQuery, searchResults, selected])

  const isCatalogSearch =
    searchQuery.trim().length >= ARTIST_SEARCH_MIN_LEN

  return (
    <>
      <div className="onb-v2-step__hero">
        <h1 className="onb-v2-step__title">
          {t('onboarding.artists.title')}
        </h1>
        <p className="onb-v2-step__subtitle">
          {t('onboarding.artists.subtitle')}
        </p>
      </div>
      <div className="onb-v2-step__body">
        {loading ? (
          <div className="onb-v2-artists-loading" />
        ) : (
          <>
            <div className="onb-v2-genre-search">
              <Icon name="search" size={15} />
              <input
                className="onb-v2-genre-search__input"
                type="search"
                enterKeyHint="search"
                placeholder={t(
                  'onboarding.artists.searchPlaceholder',
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
                  aria-label={t('onboarding.searchClear')}
                >
                  <Icon name="x" size={14} />
                </button>
              )}
            </div>
            {searchLoading && isCatalogSearch ? (
              <m.div className="onb-v2-artists-loading onb-v2-artists-loading--inline" />
            ) : null}
            <div className="onboarding-artists-grid">
              {displayedArtists.map((a) => (
                <div
                  key={a.id}
                  className={
                    [
                      'onboarding-artist-card',
                      selected.includes(a.id) ? 'selected' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')
                  }
                >
                  <button
                    type="button"
                    className="onboarding-artist-card__toggle"
                    aria-pressed={selected.includes(a.id)}
                    onClick={() => onToggle(a.id)}
                  >
                    <span className="onboarding-artist-cover-wrap">
                      <CoverImage
                        coverKey={a.image_key}
                        className="cover-image"
                      />
                    </span>
                    <span className="onboarding-artist-name">
                      {a.name}
                    </span>
                  </button>
                </div>
              ))}
              {displayedArtists.length === 0 && !searchLoading && (
                <p className="onb-v2-artists-empty">
                  {t('onboarding.artists.empty')}
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
