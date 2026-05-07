import {
  useCallback,
  useState,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { LongPressMenu } from '@/components/ui/LongPressMenu'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { hapticSelection } from '@/lib/telegram'

interface AchievementSeed {
  id: string
  icon: string
  titleKey: string
  descKey: string
  unlocked: boolean
  progress: number
  earnedAt?: string
}

/** TODO(redesign-2026): load from API when achievements endpoint exists. */
const ACHIEVEMENTS_SEED: AchievementSeed[] = [
  {
    id: 'night-owl',
    icon: 'star',
    titleKey: 'achNightOwl',
    descKey: 'achNightOwlDesc',
    unlocked: true,
    progress: 1,
    earnedAt: '2026-03-01',
  },
  {
    id: 'collector',
    icon: 'bookmark',
    titleKey: 'achCollector',
    descKey: 'achCollectorDesc',
    unlocked: true,
    progress: 1,
    earnedAt: '2026-02-14',
  },
  {
    id: 'explorer',
    icon: 'search',
    titleKey: 'achExplorer',
    descKey: 'achExplorerDesc',
    unlocked: false,
    progress: 0.62,
  },
  {
    id: 'social',
    icon: 'users-following',
    titleKey: 'achSocial',
    descKey: 'achSocialDesc',
    unlocked: false,
    progress: 0.25,
  },
  {
    id: 'streak',
    icon: 'flame',
    titleKey: 'achStreak',
    descKey: 'achStreakDesc',
    unlocked: false,
    progress: 0.4,
  },
  {
    id: 'curator',
    icon: 'library',
    titleKey: 'achCurator',
    descKey: 'achCuratorDesc',
    unlocked: true,
    progress: 1,
    earnedAt: '2026-01-20',
  },
]

export function AchievementsView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const [detail, setDetail] =
    useState<AchievementSeed | null>(null)

  const shareAchievement = useCallback(
    (a: AchievementSeed) => {
      showIsland({
        kind: 'toast',
        title: t('redesign.recap.achShareSoon'),
        durationMs: 2200,
      })
      if (a.id) void 0
    },
    [t],
  )

  const closeDetail = () => setDetail(null)

  return (
    <section
      id="view-achievements"
      className="view active rh-ach-page"
    >
      <header className="rh-ach-top">
        <MotionPress
          type="button"
          variant="ghost"
          className="rh-ach-back"
          haptic="selection"
          aria-label={t('redesign.recap.achBackAria')}
          onClick={() => navigate('/recap')}
        >
          <Icon name="chevron" size={20} className="rh-ach-back-icon" />
          <span>{t('redesign.recap.achBack')}</span>
        </MotionPress>
        <h1 className="rh-ach-title">
          {t('redesign.recap.achTitle')}
        </h1>
      </header>

      <div className="rh-ach-grid">
        {ACHIEVEMENTS_SEED.map((a) => (
          <LongPressMenu
            key={a.id}
            items={[
              {
                id: 'detail',
                label: t('redesign.recap.achMenuDetail'),
                onPick: () => setDetail(a),
              },
              {
                id: 'share',
                label: t('redesign.recap.achMenuShare'),
                onPick: () => shareAchievement(a),
              },
            ]}
          >
            <button
              type="button"
              className={[
                'glass--medium',
                'rh-ach-tile',
                a.unlocked ? 'rh-ach-tile--on' : 'rh-ach-tile--off',
              ].join(' ')}
              onClick={() => {
                hapticSelection()
                setDetail(a)
              }}
            >
              <MorphIcon
                name={a.icon}
                filled={a.unlocked}
                size={28}
                className="rh-ach-tile-icon"
              />
              <span className="rh-ach-tile-label">
                {t(`redesign.recap.${a.titleKey}`)}
              </span>
            </button>
          </LongPressMenu>
        ))}
      </div>

      <AnimatePresence>
        {detail && (
          <m.div
            key="ach-detail-overlay"
            className="rh-ach-sheet-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={TWEEN_FAST}
            onClick={closeDetail}
            role="presentation"
          >
            <m.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="ach-detail-title"
              className={[
                'glass--medium',
                'rh-ach-detail',
              ].join(' ')}
              initial={
                reduce
                  ? { opacity: 0, y: 12 }
                  : { opacity: 0, y: '18%' }
              }
              animate={
                reduce
                  ? { opacity: 1, y: 0 }
                  : { opacity: 1, y: 0 }
              }
              exit={
                reduce
                  ? { opacity: 0, y: 8 }
                  : { opacity: 0, y: '12%' }
              }
              transition={reduce ? TWEEN_FAST : SPRING_GENTLE}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="rh-ach-detail__grab" aria-hidden="true" />
              <h2 id="ach-detail-title" className="rh-ach-detail__title">
                {t(`redesign.recap.${detail.titleKey}`)}
              </h2>
              <p className="rh-ach-detail__desc">
                {t(`redesign.recap.${detail.descKey}`)}
              </p>
              <div className="rh-ach-detail__progress-track">
                <div
                  className="rh-ach-detail__progress-fill"
                  style={{
                    transform: `scaleX(${detail.progress})`,
                  }}
                />
              </div>
              {detail.unlocked && detail.earnedAt && (
                <p className="rh-ach-detail__meta">
                  {t('redesign.recap.achEarned', {
                    date: detail.earnedAt,
                  })}
                </p>
              )}
              {!detail.unlocked && (
                <p className="rh-ach-detail__meta">
                  {t('redesign.recap.achLockedHint')}
                </p>
              )}
              <MotionPress
                type="button"
                variant="primary"
                className="rh-ach-detail__close"
                onClick={closeDetail}
              >
                {t('redesign.recap.achClose')}
              </MotionPress>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    </section>
  )
}
