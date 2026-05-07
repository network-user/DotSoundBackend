import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

const REDIRECT_DELAY = 4

export function NotFoundView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [countdown, setCountdown] = useState(REDIRECT_DELAY)

  useEffect(() => {
    if (countdown <= 0) {
      navigate('/', { replace: true })
      return
    }
    const id = window.setTimeout(
      () => setCountdown((c) => c - 1),
      1000,
    )
    return () => window.clearTimeout(id)
  }, [countdown, navigate])

  return (
    <section id="view-not-found" className="view active not-found-view">
      <div className="rh-nf-panel">
        <p className="rh-nf-code" aria-hidden="true">
          404
        </p>
        <h2 className="rh-nf-title">
          {t('redesign.home.nfTitle')}
        </h2>
        <p className="rh-nf-hint">
          {t('redesign.home.nfHint', { n: countdown })}
        </p>
        <MotionPress
          variant="primary"
          className="rh-nf-home"
          onClick={() => navigate('/', { replace: true })}
        >
          <Icon name="home" size={18} />
          <span>{t('redesign.home.nfHome')}</span>
        </MotionPress>
      </div>
    </section>
  )
}
