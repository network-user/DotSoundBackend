import { useRef, type MouseEvent } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { usePreviewQueue } from '@/hooks/usePreviewQueue'

interface Props {
  availableGenres: string[]
  selectedGenres: string[]
  onToggleGenre: (g: string) => void
}

export function OnboardingGenreScreen({
  availableGenres,
  selectedGenres,
  onToggleGenre,
}: Props) {
  const { load, loading, getSegmentPath } = usePreviewQueue()
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const playingRef = useRef<string | null>(null)

  const onPlayPreview = async (genre: string, e: MouseEvent) => {
    e.stopPropagation()
    if (loading) return
    const tracks = await load(genre)
    if (!tracks.length) return
    const path = getSegmentPath(tracks[0].id)
    const a = audioRef.current
    if (!a) return
    if (playingRef.current === path) {
      a.pause()
      a.currentTime = 0
      playingRef.current = null
      return
    }
    playingRef.current = path
    a.src = path
    a.volume = 1
    a.crossOrigin = 'anonymous'
    void a.play().catch(() => {
      playingRef.current = null
    })
  }

  return (
    <div className="onboarding-step">
      <h2 className="onboarding-title">Какую музыку слушаете?</h2>
      <p className="onboarding-subtitle">
        Выберите жанры (минимум 3)
      </p>
      <div className="onboarding-chips">
        {availableGenres.map(g => (
          <div key={g} className="onboarding-genre-row">
            <button
              type="button"
              className={`onboarding-chip${
                selectedGenres.includes(g) ? ' selected' : ''
              }`}
              onClick={() => onToggleGenre(g)}
            >
              {g}
            </button>
            <button
              type="button"
              className="onboarding-genre-preview"
              onClick={ev => {
                void onPlayPreview(g, ev)
              }}
              title="Превью жанра"
              aria-label="Превью жанра"
            >
              <Icon name="play" size={16} />
            </button>
          </div>
        ))}
      </div>
      <audio ref={audioRef} className="onboarding-audio" />
    </div>
  )
}
