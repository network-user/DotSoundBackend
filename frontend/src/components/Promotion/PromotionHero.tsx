import { useEffect, useRef } from 'react'
import { api } from '@/lib/api'
import type { PromotionPublic } from '@/types/api'

interface Props {
  items: PromotionPublic[]
  onSelect: (item: PromotionPublic) => void
}

function useImpressionPing(promotionIds: number[], surface: string) {
  const sentRef = useRef<Set<number>>(new Set())
  useEffect(() => {
    for (const id of promotionIds) {
      if (sentRef.current.has(id)) continue
      sentRef.current.add(id)
      void api
        .recordPromotionEvent(id, {
          event_type: 'impression',
          surface: surface as 'hero' | 'section' | 'in_feed' | 'search_pin',
        })
        .catch(() => undefined)
    }
  }, [promotionIds, surface])
}

export function PromotionHero({ items, onSelect }: Props) {
  const ids = items.map((i) => i.id)
  useImpressionPing(ids, 'hero')

  if (items.length === 0) return null
  const first = items[0]

  const handleClick = () => {
    void api
      .recordPromotionEvent(first.id, {
        event_type: 'click',
        surface: 'hero',
      })
      .catch(() => undefined)
    onSelect(first)
  }

  return (
    <button
      type="button"
      className="promotion-hero"
      onClick={handleClick}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        border: 0,
        padding: 0,
        background: 'transparent',
        cursor: 'pointer',
      }}
      aria-label={first.title}
    >
      <div
        className="promotion-hero__inner"
        style={{
          position: 'relative',
          borderRadius: 16,
          overflow: 'hidden',
          aspectRatio: '16 / 7',
          background:
            'linear-gradient(135deg, rgba(0,0,0,0.05), rgba(0,0,0,0.25))',
        }}
      >
        {first.cover_url && (
          <img
            src={first.cover_url}
            alt=""
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
            loading="lazy"
          />
        )}
        <div
          className="promotion-hero__overlay"
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(0deg, rgba(0,0,0,0.6), rgba(0,0,0,0.1))',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
            padding: 16,
            color: '#fff',
          }}
        >
          <span
            style={{
              fontSize: 11,
              textTransform: 'uppercase',
              letterSpacing: 1,
              opacity: 0.85,
            }}
          >
            Рекомендуем
          </span>
          <h2
            style={{
              margin: '4px 0 4px 0',
              fontSize: 22,
              fontWeight: 600,
            }}
          >
            {first.title}
          </h2>
          {first.subtitle && (
            <p
              style={{
                margin: 0,
                fontSize: 14,
                opacity: 0.9,
              }}
            >
              {first.subtitle}
            </p>
          )}
          {first.cta_label && (
            <span
              style={{
                marginTop: 8,
                alignSelf: 'flex-start',
                background: 'rgba(255,255,255,0.18)',
                padding: '6px 12px',
                borderRadius: 8,
                fontSize: 13,
              }}
            >
              {first.cta_label}
            </span>
          )}
        </div>
      </div>
    </button>
  )
}
