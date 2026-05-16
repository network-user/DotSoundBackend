import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useNavigate,
  useSearchParams,
} from 'react-router-dom'

import { RecapShareCard } from '@/components/Recap/RecapShareCard'
import { RecapStoryStage } from '@/components/Recap/RecapStoryStage'
import { getRecapSnapshotMock } from '@/components/Recap/recapMock'
import { Sheet } from '@/components/ui/Sheet'
import { MotionPress } from '@/components/ui/MotionPress'
import { useBrandLabel } from '@/lib/brand'
import { isYearRecapSeasonActive } from '@/lib/recapSeason'
import { showIsland } from '@/lib/island'

import '@/styles/redesign-recap.css'

import { AchievementsView } from '@/views/AchievementsView'

export function RecapView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const brandLabel = useBrandLabel()
  const [searchParams, setSearchParams] =
    useSearchParams()
  const [shareOpen, setShareOpen] = useState(false)
  const snapshot = useMemo(
    () => getRecapSnapshotMock(),
    [],
  )

  if (searchParams.get('tab') === 'achievements') {
    return <AchievementsView />
  }

  if (!isYearRecapSeasonActive()) {
    return (
      <section
        id="view-recap"
        className="view active rh-recap-shell"
      >
        <div className="rh-recap-season-closed">
          <p className="rh-recap-season-closed__title">
            {t('redesign.recap.seasonClosedTitle')}
          </p>
          <p className="rh-recap-season-closed__hint hint">
            {t('redesign.recap.seasonClosedHint')}
          </p>
          <MotionPress
            variant="primary"
            haptic="selection"
            onClick={() => navigate('/profile')}
          >
            {t('redesign.recap.seasonClosedProfile')}
          </MotionPress>
        </div>
      </section>
    )
  }

  const savePreview = () => {
    showIsland({
      kind: 'toast',
      title: t('redesign.recap.shareSaveTodo'),
      durationMs: 2600,
    })
  }

  const sharePreview = () => {
    showIsland({
      kind: 'toast',
      title: t('redesign.recap.shareNativeTodo'),
      durationMs: 2400,
    })
  }

  return (
    <section
      id="view-recap"
      className="view active rh-recap-shell"
    >
      <RecapStoryStage
        snapshot={snapshot}
        onOpenShare={() => setShareOpen(true)}
        onOpenAchievements={() =>
          setSearchParams({ tab: 'achievements' })
        }
      />
      <Sheet
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        ariaLabel={t('redesign.recap.shareSheetAria')}
      >
        <div className="rh-share-sheet">
          <h2 className="rh-share-sheet__title">
            {t('redesign.recap.shareSheetTitle')}
          </h2>
          <p className="rh-share-sheet__hint">
            {t('redesign.recap.shareSheetHint')}
          </p>
          <div className="rh-share-sheet__preview">
            <RecapShareCard
              brandLabel={brandLabel}
              totalMinutes={snapshot.totalMinutes}
              headline={t('redesign.recap.introKicker')}
              minutesCaption={t(
                'redesign.recap.shareMinutes',
              )}
              collageSrc={snapshot.shareCoverUrls}
              saveLabel={t('redesign.recap.shareSave')}
              shareLabel={t('redesign.recap.shareAction')}
              exportTodoHint={t(
                'redesign.recap.shareExportTodo',
              )}
              onSave={savePreview}
              onShare={sharePreview}
            />
          </div>
        </div>
      </Sheet>
    </section>
  )
}
