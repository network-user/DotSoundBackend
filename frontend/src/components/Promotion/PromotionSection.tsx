import { useEffect, useRef } from 'react'
import { api } from '@/lib/api'
import type { PromotionPublic, PromotionSurface } from '@/types/api'

interface Props {
  items: PromotionPublic[]
  title?: string
  surface?: PromotionSurface
  onSelect: (item: PromotionPublic) => void
}

function usePromotionImpressionTracking(
  promotionIds: number[],
  surface: PromotionSurface,
) {
  const sentRef = useRef<Set<number>>(new Set())
  useEffect(() => {
    for (const id of promotionIds) {
      if (sentRef.current.has(id)) continue
      sentRef.current.add(id)
      void api
        .recordPromotionEvent(id, {
          event_type: 'impression',
          surface,
        })
        .catch(() => undefined)
    }
  }, [promotionIds, surface])
}

export function PromotionSection({
  items,
  title = 'Рекомендуем',
  surface = 'section',
  onSelect,
}: Props) {
  const ids = items.map((i) => i.id)
  usePromotionImpressionTracking(ids, surface)

  if (items.length === 0) return null

  const handleClick = (item: PromotionPublic) => {
    void api
      .recordPromotionEvent(item.id, {
        event_type: 'click',
        surface,
      })
      .catch(() => undefined)
    onSelect(item)
  }

  return (
    <div className="promotion-section">
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          padding: '8px 4px',
        }}
      >
        <span
          style={{
            fontSize: 15,
            fontWeight: 600,
          }}
        >
          {title}
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          gap: 12,
          overflowX: 'auto',
          paddingBottom: 8,
        }}
      >
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => handleClick(item)}
            style={{
              flex: '0 0 auto',
              width: 168,
              border: 0,
              padding: 0,
              background: 'transparent',
              textAlign: 'left',
              cursor: 'pointer',
            }}
            aria-label={item.title}
          >
            <div
              style={{
                width: '100%',
                aspectRatio: '1 / 1',
                borderRadius: 10,
                overflow: 'hidden',
                background: 'rgba(0,0,0,0.05)',
              }}
            >
              {item.cover_url && (
                <img
                  src={item.cover_url}
                  alt=""
                  loading="lazy"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                  }}
                />
              )}
            </div>
            <div
              style={{
                marginTop: 6,
                fontSize: 13,
                fontWeight: 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {item.title}
            </div>
            {item.subtitle && (
              <div
                style={{
                  fontSize: 11,
                  opacity: 0.7,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {item.subtitle}
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
