import { useState, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'

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
          'Готово. Запускаем онбординг заново.',
        ),
        durationMs: 2400,
      })
      setConfirmOpen(false)
      onClose()
      // Reload so App.tsx re-fetches onboarding status and
      // routes the user back into the wizard.
      window.setTimeout(() => {
        try {
          window.location.reload()
        } catch {
          /* ignore */
        }
      }, 300)
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

  const handleBackdrop = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !busy) setConfirmOpen(false)
  }

  return (
    <>
      <div className="settings-hint">
        {t('settings.resetRecs.sectionTitle', 'Рекомендации')}
      </div>
      <MotionPress
        type="button"
        variant="ghost"
        haptic="medium"
        className="settings-item"
        onClick={() => setConfirmOpen(true)}
      >
        <Icon name="sparkle" size={20} />
        <span>
          {t(
            'settings.resetRecs.cta',
            'Сбросить рекомендации и пройти онбординг заново',
          )}
        </span>
      </MotionPress>
      {confirmOpen && (
        <div className="modal" onClick={handleBackdrop}>
          <div className="modal-content">
            <div className="modal-header">
              <h3>
                {t(
                  'settings.resetRecs.title',
                  'Сбросить рекомендации?',
                )}
              </h3>
              <MotionPress
                type="button"
                variant="icon"
                haptic="light"
                className="icon-btn"
                ariaLabel={t('common.cancel', 'Отмена')}
                onClick={() => setConfirmOpen(false)}
                disabled={busy}
              >
                <Icon name="x" size={18} />
              </MotionPress>
            </div>
            <p className="modal-hint">
              {t(
                'settings.resetRecs.hint',
                'Жанры, дизлайки и калибровка вкуса будут очищены. Библиотека и лайкнутые треки сохранятся. Сразу после — снова пройдёте короткий онбординг, чтобы подборки стали точнее.',
              )}
            </p>
            <div className="settings-danger-zone__actions">
              <MotionPress
                type="button"
                variant="primary"
                haptic="medium"
                className="btn-primary"
                disabled={busy}
                onClick={() => void submit()}
              >
                {busy
                  ? '…'
                  : t(
                      'settings.resetRecs.confirm',
                      'Сбросить и пройти заново',
                    )}
              </MotionPress>
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="btn-secondary"
                disabled={busy}
                onClick={() => setConfirmOpen(false)}
              >
                {t('common.cancel', 'Отмена')}
              </MotionPress>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
