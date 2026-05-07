import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { getPrefetchManager } from '@/lib/prefetch/PrefetchManager'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import type { Track } from '@/types/api'

function coverUrl(key: string | null): string | null {
  if (!key) return null
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

const MOOD_ICONS = [
  'heart',
  'search',
  'flame',
  'star',
  'radio',
  'bookmark',
] as const

export function RadioView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const { track: currentTrack } = usePlayerMeta()
  const {
    startRadio,
    stopRadio,
    radioMode,
  } = usePlayerActions()

  const [historyTracks, setHistoryTracks] = useState<Track[]>([])
  const historyRef = useRef<Track[]>([])

  const heroCover = currentTrack
    ? coverUrl(currentTrack.cover_key)
    : null
  const bpm = 120

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
    if (!radioMode || !currentTrack) return
    let cancelled = false
    api
      .getRadio(currentTrack.id, 14)
      .then((res) => {
        if (cancelled || !res.tracks.length) return
        void getPrefetchManager().enqueue(res.tracks, {
          context: 'radio',
          replaceContext: true,
        })
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [radioMode, currentTrack?.id])

  const handleStartRadio = async () => {
    if (!currentTrack) return
    historyRef.current = []
    setHistoryTracks([])
    await startRadio(currentTrack)
  }

  const handleStop = () => {
    stopRadio()
  }

  // TODO(redesign-2026): когда появится mood-tagged radio API,
  // прокинуть `moodId` в `startRadio` или новый эндпойнт.
  // Сейчас mood — это quick-старт волны от текущего трека.
  const handleMood = (_moodId: string) => {
    if (!currentTrack) {
      toast.info(t('redesign.home.radioPickTrackHint'))
      return
    }
    void handleStartRadio()
  }

  const moodDefs = [
    { id: 'chill', labelKey: 'radioMoodChill', hintKey: 'radioMoodHintChill' },
    { id: 'focus', labelKey: 'radioMoodFocus', hintKey: 'radioMoodHintFocus' },
    { id: 'gym', labelKey: 'radioMoodGym', hintKey: 'radioMoodHintGym' },
    {
      id: 'cinematic',
      labelKey: 'radioMoodCinematic',
      hintKey: 'radioMoodHintCinematic',
    },
    { id: 'retro', labelKey: 'radioMoodRetro', hintKey: 'radioMoodHintRetro' },
    {
      id: 'acoustic',
      labelKey: 'radioMoodAcoustic',
      hintKey: 'radioMoodHintAcoustic',
    },
  ]

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
          <BeatPulse bpm={bpm} active={radioMode}>
            <div className="rh-radio-disc-wrap">
              {heroCover ? (
                <KenBurnsCover src={heroCover} alt="" />
              ) : (
                <div className="rh-radio-disc-placeholder">
                  <Icon name="radio" size={48} />
                </div>
              )}
            </div>
          </BeatPulse>
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
