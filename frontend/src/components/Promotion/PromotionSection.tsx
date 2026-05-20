import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import type { PromotionPublic, PromotionSurface } from '@/types/api'
import '@/styles/promotion.css'

interface Props {
  items: PromotionPublic[]
  title?: string
  surface?: PromotionSurface
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
    // sessionStorage unavailable — extra impressions tolerated.
  }
}

function usePromotionImpressionTracking(
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

export function PromotionSection({
  items,
  title,
  surface = 'section',
  onSelect,
}: Props) {
  const { t } = useTranslation()
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

  const headingText = title ?? t('promotion.sectionTitle', 'Рекомендуем')

  return (
    <div className="promotion-section">
      <div className="promotion-section__header">
        <span className="promotion-section__title">{headingText}</span>
      </div>
      <div className="promotion-section__row">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className="promotion-card"
            onClick={() => handleClick(item)}
            aria-label={item.title}
          >
            <div className="promotion-card__cover">
              {item.cover_url && (
                <img src={item.cover_url} alt="" loading="lazy" />
              )}
            </div>
            <div className="promotion-card__title">{item.title}</div>
            {item.subtitle && (
              <div className="promotion-card__subtitle">{item.subtitle}</div>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
