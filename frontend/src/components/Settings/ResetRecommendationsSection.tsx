import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { SettingsConfirmModal } from './SettingsConfirmModal'

interface Props {
  onClose: () => void
}

export function ResetRecommendationsSection({ onClose }: Props) {
  const { t } = useTranslation()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (busy) return
    setBusy(true)
    try {
      await api.replayOnboarding()
      showIsland({
        kind: 'toast',
        title: t(
          'settings.resetRecs.done',
          'Рекомендации сброшены',
        ),
        durationMs: 2400,
      })
      setConfirmOpen(false)
      onClose()
      window.dispatchEvent(
        new Event('ds-recommendations-reset'),
      )
    } catch {
      showIsland({
        kind: 'error',
        title: t(
          'settings.resetRecs.fail',
          'Не удалось сбросить — попробуйте ещё раз',
        ),
        durationMs: 3000,
      })
      setBusy(false)
    }
  }

  return (
    <>
      <div className="settings-section-header">
        {t('settings.resetRecs.sectionTitle', 'Рекомендации')}
      </div>
      <MotionPress
        type="button"
        variant="ghost"
        haptic="medium"
        className="settings-item"
        onClick={(e) => {
          e.stopPropagation()
          setConfirmOpen(true)
        }}
      >
        <Icon name="sparkle" size={20} />
        <span>
          {t(
            'settings.resetRecs.cta',
            'Сбросить рекомендации',
          )}
        </span>
        <Icon
          name="chevron"
          size={16}
          className="settings-chevron"
        />
      </MotionPress>
      <SettingsConfirmModal
        open={confirmOpen}
        onClose={() => {
          if (!busy) setConfirmOpen(false)
        }}
        title={t(
          'settings.resetRecs.title',
          'Сбросить рекомендации?',
        )}
        hint={t(
          'settings.resetRecs.hint',
          'Очистим жанровые предпочтения, дизлайки и калибровку вкуса. Библиотека и лайки останутся без изменений.',
        )}
        confirmLabel={t(
          'settings.resetRecs.confirm',
          'Сбросить',
        )}
        cancelLabel={t('common.cancel', 'Отмена')}
        busy={busy}
        onConfirm={() => void submit()}
      />
    </>
  )
}
