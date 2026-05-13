import { useState, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
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
          'Рекомендации сброшены',
        ),
        durationMs: 2400,
      })
      setConfirmOpen(false)
      onClose()
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
      {confirmOpen &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            className="modal settings-reset-modal"
            onClick={handleBackdrop}
          >
            <div
              className="modal-content settings-reset-modal__panel"
              onClick={(e) => e.stopPropagation()}
            >
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
              <p className="modal-hint settings-reset-modal__hint">
                {t(
                  'settings.resetRecs.hint',
                  'Очистим жанровые предпочтения, дизлайки и калибровку вкуса. Библиотека и лайки останутся без изменений.',
                )}
              </p>
              <div className="settings-danger-zone__actions settings-reset-modal__actions">
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
                        'Сбросить',
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
          </div>,
          document.body,
        )}
    </>
  )
}
