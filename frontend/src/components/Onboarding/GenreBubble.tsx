import { useMemo } from 'react'
import { Icon } from '@/components/Icon/Icon'
import type { OnboardingGenreBubble } from '@/types/api'

interface Props {
  bubble: OnboardingGenreBubble
  selected: boolean
  isPlaying?: boolean
  isLoading?: boolean
  onToggle: (genre: string) => void
  onTogglePreview: (genre: string) => void
}

function coverUrl(key: string): string {
  return `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(key)}`
}

export function GenreBubble({
  bubble,
  selected,
  isPlaying = false,
  isLoading = false,
  onToggle,
  onTogglePreview,
}: Props) {
  const covers = useMemo(
    () => bubble.sample_cover_keys.slice(0, 4),
    [bubble.sample_cover_keys],
  )

  const renderCover = () => {
    if (covers.length === 0) {
      return (
        <span
          className="onb-v2-bubble__cover onb-v2-bubble__cover--placeholder"
          aria-hidden="true"
        />
      )
    }
    if (covers.length === 1) {
      return (
        <span
          className="onb-v2-bubble__cover onb-v2-bubble__cover--single"
          aria-hidden="true"
        >
          <img
            src={coverUrl(covers[0])}
            alt=""
            className="onb-v2-bubble__cover-img"
            loading="lazy"
            decoding="async"
            draggable={false}
          />
        </span>
      )
    }
    return (
      <span className="onb-v2-bubble__cover" aria-hidden="true">
        {covers.map((key, i) => (
          <img
            key={`${key}-${i}`}
            src={coverUrl(key)}
            alt=""
            className="onb-v2-bubble__cover-img"
            loading="lazy"
            decoding="async"
            draggable={false}
          />
        ))}
      </span>
    )
  }

  const stateClass = [
    'onb-v2-bubble',
    selected ? 'is-selected' : '',
    isPlaying ? 'is-playing' : '',
    isLoading ? 'is-loading' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      type="button"
      className={stateClass}
      onClick={() => onToggle(bubble.genre)}
      aria-pressed={selected}
    >
      {renderCover()}
      <span
        className="onb-v2-bubble__cover-fade"
        aria-hidden="true"
      />
      <span
        role="button"
        tabIndex={0}
        className={[
          'onb-v2-bubble__preview-btn',
          isPlaying ? 'is-playing' : '',
          isLoading ? 'is-loading' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        aria-label={
          isPlaying ? 'Stop preview' : 'Play preview'
        }
        onClick={(e) => {
          e.stopPropagation()
          onTogglePreview(bubble.genre)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            e.stopPropagation()
            onTogglePreview(bubble.genre)
          }
        }}
      >
        {isLoading ? (
          <span className="onb-v2-bubble__preview-spinner" />
        ) : (
          <Icon
            name={isPlaying ? 'pause' : 'play'}
            size={14}
          />
        )}
      </span>
      <span className="onb-v2-bubble__name">
        {bubble.genre}
      </span>
      {selected && (
        <span
          className="onb-v2-bubble__check"
          aria-hidden="true"
        >
          ✓
        </span>
      )}
    </button>
  )
}
