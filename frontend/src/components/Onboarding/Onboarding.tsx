import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import type { Track } from '@/types/api'

interface Props {
  onComplete: () => void
}

type Step = 'genres' | 'artists' | 'moods' | 'calibration'

const MOODS = [
  { id: 'chill', label: 'Chill' },
  { id: 'energetic', label: 'Energetic' },
  { id: 'sad', label: 'Sad' },
  { id: 'happy', label: 'Happy' },
  { id: 'focus', label: 'Focus' },
  { id: 'party', label: 'Party' },
]

export function Onboarding({ onComplete }: Props) {
  const [step, setStep] = useState<Step>('genres')
  const [genres, setGenres] = useState<string[]>([])
  const [availableGenres, setAvailableGenres] = useState<string[]>([])
  const [artists, setArtists] = useState<{ id: number; name: string; image_key: string | null }[]>([])
  const [selectedArtists, setSelectedArtists] = useState<number[]>([])
  const [selectedMoods, setSelectedMoods] = useState<string[]>([])
  const [calibrationTracks, setCalibrationTracks] = useState<Track[]>([])
  const [calibrationResults, setCalibrationResults] = useState<Record<number, boolean>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getOnboardingGenres().then(setAvailableGenres).catch(() => {})
  }, [])

  const loadArtists = useCallback((selectedGenres: string[]) => {
    api.getOnboardingArtists(selectedGenres).then(setArtists).catch(() => {})
  }, [])

  const toggleGenre = (g: string) => {
    setGenres(prev => prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g])
  }

  const toggleArtist = (id: number) => {
    setSelectedArtists(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const toggleMood = (m: string) => {
    setSelectedMoods(prev => prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m])
  }

  const handleNext = async () => {
    if (step === 'genres') {
      loadArtists(genres)
      setStep('artists')
    } else if (step === 'artists') {
      setStep('moods')
    } else if (step === 'moods') {
      setSaving(true)
      try {
        await api.saveOnboardingPreferences({
          genres,
          artist_ids: selectedArtists,
          moods: selectedMoods,
        })
        const tracks = await api.getCalibrationTracks()
        setCalibrationTracks(tracks)
        setStep('calibration')
      } catch { }
      setSaving(false)
    } else if (step === 'calibration') {
      setSaving(true)
      try {
        const items = Object.entries(calibrationResults).map(([tid, liked]) => ({
          track_id: Number(tid),
          liked,
        }))
        if (items.length > 0) {
          await api.saveCalibration(items)
        }
        await api.completeOnboarding()
        onComplete()
      } catch { }
      setSaving(false)
    }
  }

  const handleSkip = async () => {
    setSaving(true)
    try {
      await api.completeOnboarding()
      onComplete()
    } catch { }
    setSaving(false)
  }

  const stepIndex = ['genres', 'artists', 'moods', 'calibration'].indexOf(step)

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-container">
        <div className="onboarding-progress">
          {[0, 1, 2, 3].map(i => (
            <div
              key={i}
              className={`onboarding-dot${i <= stepIndex ? ' active' : ''}`}
            />
          ))}
        </div>

        {step === 'genres' && (
          <div className="onboarding-step">
            <h2 className="onboarding-title">
              Какую музыку слушаете?
            </h2>
            <p className="onboarding-subtitle">
              Выберите жанры (минимум 3)
            </p>
            <div className="onboarding-chips">
              {availableGenres.map(g => (
                <button
                  key={g}
                  className={`onboarding-chip${genres.includes(g) ? ' selected' : ''}`}
                  onClick={() => toggleGenre(g)}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
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
                <button
                  key={a.id}
                  className={`onboarding-artist-card${selectedArtists.includes(a.id) ? ' selected' : ''}`}
                  onClick={() => toggleArtist(a.id)}
                >
                  {a.image_key ? (
                    <CoverImage coverKey={a.image_key} />
                  ) : (
                    <div className="onboarding-artist-placeholder">
                      <Icon name="user" size={24} />
                    </div>
                  )}
                  <span className="onboarding-artist-name">{a.name}</span>
                </button>
              ))}
              {artists.length === 0 && (
                <p className="onboarding-empty">
                  Артисты появятся по мере наполнения каталога
                </p>
              )}
            </div>
          </div>
        )}

        {step === 'moods' && (
          <div className="onboarding-step">
            <h2 className="onboarding-title">
              Настроение
            </h2>
            <p className="onboarding-subtitle">
              Какую атмосферу предпочитаете?
            </p>
            <div className="onboarding-chips">
              {MOODS.map(m => (
                <button
                  key={m.id}
                  className={`onboarding-chip${selectedMoods.includes(m.id) ? ' selected' : ''}`}
                  onClick={() => toggleMood(m.id)}
                >
                  {m.label}
                </button>
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
              Это поможет подобрать музыку для вас
            </p>
            <div className="onboarding-calibration-list">
              {calibrationTracks.map(t => (
                <div key={t.id} className="onboarding-calibration-item">
                  <CoverImage coverKey={t.cover_key} />
                  <div className="onboarding-calibration-info">
                    <span className="onboarding-calibration-title">{t.title}</span>
                    <span className="onboarding-calibration-artist">{t.artist ?? '—'}</span>
                  </div>
                  <div className="onboarding-calibration-actions">
                    <button
                      className={`icon-btn${calibrationResults[t.id] === true ? ' active' : ''}`}
                      onClick={() => setCalibrationResults(prev => ({ ...prev, [t.id]: true }))}
                    >
                      <Icon name="heart" size={20} />
                    </button>
                    <button
                      className={`icon-btn${calibrationResults[t.id] === false ? ' active' : ''}`}
                      onClick={() => setCalibrationResults(prev => ({ ...prev, [t.id]: false }))}
                    >
                      <Icon name="thumbs-down" size={20} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="onboarding-footer">
          <button
            className="onboarding-skip"
            onClick={handleSkip}
            disabled={saving}
          >
            Пропустить
          </button>
          <button
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
                : 'Далее'
            }
          </button>
        </div>
      </div>
    </div>
  )
}
