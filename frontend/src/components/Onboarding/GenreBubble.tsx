import { useMemo } from 'react'
import { coverProxyUrl } from '@/lib/coverProxy'
import type { OnboardingGenreBubble } from '@/types/api'

interface Props {
  bubble: OnboardingGenreBubble
  selected: boolean
  onToggle: (genre: string) => void
}

function coverUrl(key: string): string {
  return coverProxyUrl(key, { width: 120 })
}

export function GenreBubble({
  bubble,
  selected,
  onToggle,
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
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={stateClass}>
      <button
        type="button"
        className="onb-v2-bubble__toggle"
        onClick={() => onToggle(bubble.genre)}
        aria-pressed={selected}
      >
        {renderCover()}
        <span
          className="onb-v2-bubble__cover-fade"
          aria-hidden="true"
        />
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
    </div>
  )
}
