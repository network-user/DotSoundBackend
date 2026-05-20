import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import type { PromotionPublic, PromotionSurface } from '@/types/api'
import '@/styles/promotion.css'

interface Props {
  items: PromotionPublic[]
  onSelect: (item: PromotionPublic) => void
}

function impressionKey(
  promotionId: number,
  surface: PromotionSurface,
): string {
  return `dotsound.promo.imp.${surface}.${promotionId}`
}

function alreadySent(
  promotionId: number,
  surface: PromotionSurface,
): boolean {
  try {
    return (
      window.sessionStorage.getItem(impressionKey(promotionId, surface)) !==
      null
    )
  } catch {
    return false
  }
}

function markSent(
  promotionId: number,
  surface: PromotionSurface,
): void {
  try {
    window.sessionStorage.setItem(
      impressionKey(promotionId, surface),
      String(Date.now()),
    )
  } catch {
    // sessionStorage unavailable (private mode etc) — fall back to
    // best-effort: extra impressions are tolerated.
  }
}

function useImpressionPing(
  promotionIds: number[],
  surface: PromotionSurface,
) {
  const localSentRef = useRef<Set<number>>(new Set())
  useEffect(() => {
    for (const id of promotionIds) {
      if (localSentRef.current.has(id)) continue
      if (alreadySent(id, surface)) {
        localSentRef.current.add(id)
        continue
      }
      localSentRef.current.add(id)
      markSent(id, surface)
      void api
        .recordPromotionEvent(id, {
          event_type: 'impression',
          surface,
        })
        .catch(() => undefined)
    }
  }, [promotionIds, surface])
}

export function PromotionHero({ items, onSelect }: Props) {
  const { t } = useTranslation()
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
      aria-label={first.title}
    >
      <div className="promotion-hero__inner">
        {first.cover_url && (
          <img
            className="promotion-hero__cover"
            src={first.cover_url}
            alt=""
            loading="lazy"
          />
        )}
        <div className="promotion-hero__overlay">
          <span className="promotion-hero__kicker">
            {t('promotion.kicker', 'Рекомендуем')}
          </span>
          <h2 className="promotion-hero__title">{first.title}</h2>
          {first.subtitle && (
            <p className="promotion-hero__subtitle">{first.subtitle}</p>
          )}
          {first.cta_label && (
            <span className="promotion-hero__cta">{first.cta_label}</span>
          )}
        </div>
      </div>
    </button>
  )
}
