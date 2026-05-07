import { useRef, type MouseEvent } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
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
    void a
      .play()
      .catch((e: unknown) => {
        if (
          e &&
          typeof e === 'object' &&
          'name' in e &&
          (e as { name: string }).name ===
            'AbortError'
        ) {
          return
        }
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
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className={`onboarding-chip${
                selectedGenres.includes(g) ? ' selected' : ''
              }`}
              onClick={() => onToggleGenre(g)}
            >
              {g}
            </MotionPress>
            <MotionPress
              type="button"
              variant="icon"
              haptic="light"
              className="onboarding-genre-preview"
              ariaLabel="Превью жанра"
              onClick={ev => {
                void onPlayPreview(g, ev as MouseEvent)
              }}
            >
              <Icon name="play" size={16} />
            </MotionPress>
          </div>
        ))}
      </div>
      <audio ref={audioRef} className="onboarding-audio" />
    </div>
  )
}
