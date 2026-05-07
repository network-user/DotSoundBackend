import { useCallback, useEffect, useState, useRef } from 'react'
import { AnimatePresence } from 'framer-motion'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { OnboardingImportStep } from '@/components/Onboarding/OnboardingImportStep'
import { OnboardingGenreScreen } from '@/components/Onboarding/OnboardingGenreScreen'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { useTranslation } from 'react-i18next'
import { showIsland } from '@/lib/island'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { trackActivationEvent } from '@/lib/activation'
import type { Track } from '@/types/api'

interface Props {
  onComplete: () => void
}

type Step = 'import' | 'genres' | 'artists' | 'moods' | 'calibration'
type CalibrationChoice = 'like' | 'dislike' | 'skip'
type OnboardingDraft = {
  step: Step
  includeImport: boolean
  genres: string[]
  selectedArtists: number[]
  selectedMoods: string[]
  calibrationResults: Record<number, CalibrationChoice>
}

const ONBOARDING_DRAFT_KEY = 'onboarding:draft:v1'

const MOODS = [
  { id: 'chill', label: 'Chill' },
  { id: 'energetic', label: 'Energetic' },
  { id: 'sad', label: 'Sad' },
  { id: 'happy', label: 'Happy' },
  { id: 'focus', label: 'Focus' },
  { id: 'party', label: 'Party' },
]

const STEP_HINTS: Record<Step, { reason: string; etaSec: number }> = {
  import: {
    reason: 'Перенесёт вашу музыку — ничего не теряем',
    etaSec: 90,
  },
  genres: {
    reason: 'Помогает сразу собрать главную страницу',
    etaSec: 30,
  },
  artists: {
    reason: 'Подключим радио и подписки автоматически',
    etaSec: 30,
  },
  moods: {
    reason: 'Подскажет, под какое настроение играть',
    etaSec: 15,
  },
  calibration: {
    reason: 'Настроит подборки за пару кликов',
    etaSec: 30,
  },
}

function formatEtaSeconds(sec: number): string {
  if (sec <= 0) return '<1 сек'
  if (sec < 60) return `~${sec} сек`
  const min = Math.round(sec / 60)
  return `~${min} мин`
}

export function Onboarding({ onComplete }: Props) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const [includeImport, setIncludeImport] = useState(false)
  const [step, setStep] = useState<Step>('genres')
  const prevStepRef = useRef<Step>('genres')
  const directionRef = useRef<1 | -1>(1)
  const [genres, setGenres] = useState<string[]>([])
  const [availableGenres, setAvailableGenres] = useState<string[]>([])
  const [artists, setArtists] = useState<
    { id: number; name: string; image_key: string | null }[]
  >([])
  const [selectedArtists, setSelectedArtists] = useState<number[]>([])
  const [selectedMoods, setSelectedMoods] = useState<string[]>([])
  const [calibrationTracks, setCalibrationTracks] = useState<Track[]>([])
  const [calibrationResults, setCalibrationResults] = useState<
    Record<number, CalibrationChoice>
  >({})
  const [saving, setSaving] = useState(false)

  const [playingTrackId, setPlayingTrackId] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const loadCalibrationTracks = useCallback(async () => {
    const tracks = await api.getCalibrationTracks()
    setCalibrationTracks(tracks)
  }, [])

  const playSnippet = async (trackId: number) => {
    if (playingTrackId === trackId) {
      if (audioRef.current && !audioRef.current.paused) {
        audioRef.current.pause()
      } else if (audioRef.current) {
        audioRef.current.play().catch(() => {})
      }
      return
    }
    setPlayingTrackId(trackId)
    if (audioRef.current) {
      audioRef.current.src = `/api/v1/track-preview/${trackId}/segment.m4a`
      audioRef.current.play().catch(() => setPlayingTrackId(null))
    }
  }

  useEffect(() => {
    const parseDraft = (): OnboardingDraft | null => {
      try {
        const raw = localStorage.getItem(ONBOARDING_DRAFT_KEY)
        if (!raw) return null
        return JSON.parse(raw) as OnboardingDraft
      } catch {
        return null
      }
    }

    const restoreDraft = (
      draft: OnboardingDraft,
      useImportStep: boolean,
    ) => {
      setGenres(Array.isArray(draft.genres) ? draft.genres : [])
      setSelectedArtists(
        Array.isArray(draft.selectedArtists)
          ? draft.selectedArtists
          : [],
      )
      setSelectedMoods(
        Array.isArray(draft.selectedMoods) ? draft.selectedMoods : [],
      )
      setCalibrationResults(draft.calibrationResults ?? {})
      if (useImportStep) {
        setStep(draft.step)
      } else {
        setStep(draft.step === 'import' ? 'genres' : draft.step)
      }
    }

    api
      .getOnboardingStatus()
      .then(s => {
        const draft = parseDraft()
        if (!s.import_prompt_acknowledged) {
          setIncludeImport(true)
          if (draft) {
            restoreDraft(draft, true)
          } else {
            setStep('import')
          }
        } else {
          setIncludeImport(false)
          if (draft) {
            restoreDraft(draft, false)
          } else {
            setStep('genres')
          }
        }
      })
      .catch(() => {
        setIncludeImport(false)
        setStep('genres')
      })
  }, [])

  useEffect(() => {
    const draft: OnboardingDraft = {
      step,
      includeImport,
      genres,
      selectedArtists,
      selectedMoods,
      calibrationResults,
    }
    try {
      localStorage.setItem(
        ONBOARDING_DRAFT_KEY,
        JSON.stringify(draft),
      )
    } catch {
      /* ignore */
    }
  }, [
    step,
    includeImport,
    genres,
    selectedArtists,
    selectedMoods,
    calibrationResults,
  ])

  useEffect(() => {
    api.getOnboardingGenres().then(setAvailableGenres).catch(() => {})
  }, [])

  const loadArtists = useCallback(
    (selectedGenres: string[]) => {
      api
        .getOnboardingArtists(selectedGenres)
        .then(setArtists)
        .catch(() => {})
    },
    [],
  )

  const onImportDone = useCallback(() => {
    setStep('genres')
  }, [])

  const toggleGenre = (g: string) => {
    setGenres(prev =>
      prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g],
    )
  }

  const toggleArtist = (id: number) => {
    setSelectedArtists(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    )
  }

  const toggleMood = (m: string) => {
    setSelectedMoods(prev =>
      prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m],
    )
  }

  const stepOrder: Step[] = includeImport
    ? ['import', 'genres', 'artists', 'moods', 'calibration']
    : ['genres', 'artists', 'moods', 'calibration']

  const handleNext = async () => {
    if (step === 'genres') {
      trackActivationEvent('onboarding_step_complete', {
        meta: { step: 'genres', count: genres.length },
      })
      showIsland({
        kind: 'toast',
        title: t('redesign.onboardingMsg.genresDone', { count: genres.length }),
        durationMs: 2400,
      })
      loadArtists(genres)
      setStep('artists')
    } else if (step === 'artists') {
      trackActivationEvent('onboarding_step_complete', {
        meta: {
          step: 'artists',
          count: selectedArtists.length,
        },
      })
      if (selectedArtists.length) {
        showIsland({
          kind: 'toast',
          title: t('redesign.onboardingMsg.artistsDone', { count: selectedArtists.length }),
          durationMs: 2400,
        })
      }
      setStep('moods')
    } else if (step === 'moods') {
      setSaving(true)
      try {
        await api.saveOnboardingPreferences({
          genres,
          artist_ids: selectedArtists,
          moods: selectedMoods,
        })
        trackActivationEvent('onboarding_step_complete', {
          meta: {
            step: 'moods',
            count: selectedMoods.length,
          },
        })
        showIsland({
          kind: 'toast',
          title: t('redesign.onboardingMsg.profileSaved'),
          durationMs: 2400,
        })
        await loadCalibrationTracks()
        setStep('calibration')
      } catch {
        showIsland({
          kind: 'error',
          title: t('redesign.onboardingMsg.saveFail'),
          durationMs: 3500,
        })
      }
      setSaving(false)
    } else if (step === 'calibration') {
      setSaving(true)
      try {
        const items = Object.entries(calibrationResults).map(
          ([tid, choice]) =>
            choice === 'like'
              ? {
                  track_id: Number(tid),
                  liked: true,
                }
              : choice === 'dislike'
                ? {
                    track_id: Number(tid),
                    liked: false,
                  }
                : null,
        )
        const filteredItems = items.filter(
          (item): item is { track_id: number; liked: boolean } =>
            item !== null,
        )
        if (filteredItems.length > 0) {
          await api.saveCalibration(filteredItems)
        }
        await api.completeOnboarding()
        trackActivationEvent('onboarding_complete', {
          meta: { calibrated: filteredItems.length },
        })
        showIsland({
          kind: 'toast',
          title: t('redesign.onboardingMsg.calibrationDone'),
          durationMs: 2400,
        })
        localStorage.removeItem(ONBOARDING_DRAFT_KEY)
        onComplete()
      } catch {
        showIsland({
          kind: 'error',
          title: t('redesign.onboardingMsg.finishFail'),
          durationMs: 3500,
        })
      }
      setSaving(false)
    }
  }

  const handleSkip = async () => {
    if (step === 'import') return
    setSaving(true)
    try {
      const res = await api.smartSkipOnboarding()
      trackActivationEvent('onboarding_skip', {
        meta: {
          step,
          applied_genres: res.applied_genres.length,
        },
      })
      if (res.applied_genres.length) {
        showIsland({
          kind: 'toast',
          title: t('redesign.onboardingMsg.smartGenresApplied'),
          durationMs: 3500,
        })
      } else if (!res.enabled) {
        showIsland({
          kind: 'toast',
          title: t('redesign.onboardingMsg.smartDisabled'),
          durationMs: 3500,
        })
      } else {
        showIsland({
          kind: 'toast',
          title: t('redesign.onboardingMsg.smartFallback'),
          durationMs: 3500,
        })
      }
      localStorage.removeItem(ONBOARDING_DRAFT_KEY)
      onComplete()
    } catch {
      try {
        await api.completeOnboarding()
        localStorage.removeItem(ONBOARDING_DRAFT_KEY)
        onComplete()
      } catch {
        showIsland({
          kind: 'error',
          title: t('redesign.onboardingMsg.skipFail'),
          durationMs: 3500,
        })
      }
    }
    setSaving(false)
  }

  const handleLoadMoreCalibration = useCallback(async () => {
    if (saving) return
    setSaving(true)
    try {
      const next = await api.getCalibrationTracks()
      setCalibrationTracks(prev => {
        const seen = new Set(prev.map(t => t.id))
        return [...prev, ...next.filter(t => !seen.has(t.id))]
      })
    } catch {
      /* ignore */
    }
    setSaving(false)
  }, [saving])

  const stepIndex = stepOrder.indexOf(step)
  const dotCount = stepOrder.length

  useEffect(() => {
    const prevIdx = stepOrder.indexOf(prevStepRef.current)
    if (prevIdx >= 0 && stepIndex >= 0) {
      directionRef.current = stepIndex >= prevIdx ? 1 : -1
    }
    prevStepRef.current = step
  }, [step, stepIndex, stepOrder])

  const slideVariants = reduceMotion
    ? {
        initial: { opacity: 0 },
        animate: { opacity: 1 },
        exit: { opacity: 0 },
      }
    : {
        initial: (dir: 1 | -1) => ({
          x: dir === 1 ? '8%' : '-8%',
          opacity: 0,
        }),
        animate: { x: 0, opacity: 1 },
        exit: (dir: 1 | -1) => ({
          x: dir === 1 ? '-8%' : '8%',
          opacity: 0,
        }),
      }
  const remainingSec = stepOrder
    .slice(stepIndex)
    .reduce((acc, s) => acc + STEP_HINTS[s].etaSec, 0)
  const stepHint = STEP_HINTS[step]

  useEffect(() => {
    trackActivationEvent('onboarding_step_view', {
      meta: { step },
    })
  }, [step])

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-container">
        <div
          className="onboarding-progress-meta"
          aria-live="polite"
        >
          <span className="onboarding-progress-meta__step">
            Шаг {stepIndex + 1} из {dotCount}
          </span>
          <span className="onboarding-progress-meta__sep">
            ·
          </span>
          <span className="onboarding-progress-meta__time">
            {formatEtaSeconds(remainingSec)} осталось
          </span>
        </div>
        <div className="onboarding-progress">
          {Array.from({ length: dotCount }, (_, i) => (
            <div
              key={i}
              className={`onboarding-dot${
                i <= stepIndex ? ' active' : ''
              }`}
            />
          ))}
        </div>
        <div className="onboarding-progress-hint">
          {stepHint.reason}
        </div>

        <AnimatePresence
          mode="wait"
          custom={directionRef.current}
        >
          <m.div
            key={step}
            custom={directionRef.current}
            variants={slideVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={
              reduceMotion ? TWEEN_FAST : SPRING_GENTLE
            }
            className="onboarding-step-wrap re-onb-step-wrap"
          >
            {step === 'import' && (
              <OnboardingImportStep onDone={onImportDone} />
            )}

            {step === 'genres' && (
              <OnboardingGenreScreen
                availableGenres={availableGenres}
                selectedGenres={genres}
                onToggleGenre={toggleGenre}
              />
            )}

            {step === 'artists' && (
              <div className="onboarding-step">
                <h2 className="onboarding-title">
                  Любимые исполнители
                </h2>
                <p className="onboarding-subtitle">
                  Выберите исполнителей или пропустите
                </p>
                <div className="onboarding-artists-grid">
                  {artists.map(a => (
                    <MotionPress
                      key={a.id}
                      type="button"
                      variant="ghost"
                      haptic="light"
                      className={`onboarding-artist-card${
                        selectedArtists.includes(a.id)
                          ? ' selected'
                          : ''
                      }`}
                      onClick={() => toggleArtist(a.id)}
                    >
                      {a.image_key ? (
                        <CoverImage coverKey={a.image_key} />
                      ) : (
                        <div className="onboarding-artist-placeholder">
                          <Icon name="user" size={24} />
                        </div>
                      )}
                      <span className="onboarding-artist-name">
                        {a.name}
                      </span>
                    </MotionPress>
                  ))}
                  {artists.length === 0 && (
                    <p className="onboarding-empty">
                      Артисты появятся по мере наполнения
                      каталога
                    </p>
                  )}
                </div>
              </div>
            )}

            {step === 'moods' && (
              <div className="onboarding-step">
                <h2 className="onboarding-title">Настроение</h2>
                <p className="onboarding-subtitle">
                  Какую атмосферу предпочитаете?
                </p>
                <div className="onboarding-chips">
                  {MOODS.map(mood => (
                    <MotionPress
                      key={mood.id}
                      type="button"
                      variant="ghost"
                      haptic="light"
                      className={`onboarding-chip${
                        selectedMoods.includes(mood.id)
                          ? ' selected'
                          : ''
                      }`}
                      onClick={() => toggleMood(mood.id)}
                    >
                      {mood.label}
                    </MotionPress>
                  ))}
                </div>
              </div>
            )}

            {step === 'calibration' && (
              <div className="onboarding-step">
                <h2 className="onboarding-title">
                  Оцените треки
                </h2>
                <p className="onboarding-subtitle">
                  Это поможет подобрать музыку для вас.
                  Нажмите на трек, чтобы прослушать превью.
                </p>
                <div className="onboarding-calibration-list">
                  {calibrationTracks.map(tr => (
                    <div
                      key={tr.id}
                      className={`onboarding-calibration-item re-onb-cal-item${
                        playingTrackId === tr.id
                          ? ' playing'
                          : ''
                      }`}
                    >
                      <MotionPress
                        type="button"
                        variant="ghost"
                        haptic="light"
                        className="onboarding-calibration-play-area re-onb-cal-play"
                        onClick={() => playSnippet(tr.id)}
                      >
                        <div className="re-onb-cal-cover">
                          <CoverImage
                            coverKey={tr.cover_key}
                          />
                          {playingTrackId === tr.id && (
                            <div className="re-onb-cal-cover-overlay">
                              <MorphIcon
                                name="pause"
                                size={22}
                                filled
                              />
                            </div>
                          )}
                        </div>
                        <div className="onboarding-calibration-info">
                          <span className="onboarding-calibration-title">
                            {tr.title}
                          </span>
                          <span className="onboarding-calibration-artist">
                            {tr.artist ?? '—'}
                          </span>
                        </div>
                      </MotionPress>
                      <div className="onboarding-calibration-actions">
                        <MotionPress
                          type="button"
                          variant="icon"
                          haptic="light"
                          className={`icon-btn${
                            calibrationResults[tr.id] ===
                            'like'
                              ? ' active'
                              : ''
                          }`}
                          onClick={() =>
                            setCalibrationResults(prev => ({
                              ...prev,
                              [tr.id]: 'like',
                            }))
                          }
                        >
                          <MorphIcon
                            name="heart"
                            size={20}
                            filled={
                              calibrationResults[tr.id] ===
                              'like'
                            }
                          />
                        </MotionPress>
                        <MotionPress
                          type="button"
                          variant="icon"
                          haptic="light"
                          className={`icon-btn${
                            calibrationResults[tr.id] ===
                            'dislike'
                              ? ' active'
                              : ''
                          }`}
                          onClick={() =>
                            setCalibrationResults(prev => ({
                              ...prev,
                              [tr.id]: 'dislike',
                            }))
                          }
                        >
                          <Icon
                            name="thumbs-down"
                            size={20}
                          />
                        </MotionPress>
                        <MotionPress
                          type="button"
                          variant="icon"
                          haptic="light"
                          className={`icon-btn${
                            calibrationResults[tr.id] ===
                            'skip'
                              ? ' active'
                              : ''
                          }`}
                          onClick={() =>
                            setCalibrationResults(prev => ({
                              ...prev,
                              [tr.id]: 'skip',
                            }))
                          }
                          ariaLabel="Нейтрально, пропустить"
                        >
                          <Icon name="x" size={18} />
                        </MotionPress>
                      </div>
                    </div>
                  ))}
                </div>
                {calibrationTracks.length > 0 && (
                  <MotionPress
                    type="button"
                    variant="ghost"
                    haptic="light"
                    className="btn-secondary re-onb-cal-more"
                    onClick={handleLoadMoreCalibration}
                    disabled={saving}
                  >
                    Показать другие треки
                  </MotionPress>
                )}
              </div>
            )}
          </m.div>
        </AnimatePresence>

        {step !== 'import' && (
          <div className="onboarding-footer">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="onboarding-skip"
              onClick={handleSkip}
              disabled={saving}
            >
              Пропустить
            </MotionPress>
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="onboarding-next"
              onClick={handleNext}
              disabled={
                saving ||
                (step === 'genres' && genres.length < 3)
              }
            >
              {saving
                ? 'Сохранение...'
                : step === 'calibration'
                  ? 'Готово'
                  : 'Далее'}
            </MotionPress>
          </div>
        )}
      </div>
      <audio
        ref={audioRef}
        onEnded={() => setPlayingTrackId(null)}
        preload="none"
        className="re-onb-hidden-audio"
      />
    </div>
  )
}
