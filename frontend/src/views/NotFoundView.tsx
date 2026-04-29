import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

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
      <div className="not-found-content">
        <p className="not-found-code">404</p>
        <h2 className="not-found-title">
          {t('notFound.title', 'Страница не найдена')}
        </h2>
        <p className="not-found-hint">
          {t('notFound.redirect', 'Переход через {{n}} с…', {
            n: countdown,
          })}
        </p>
        <button
          className="not-found-home-btn"
          onClick={() => navigate('/', { replace: true })}
        >
          {t('notFound.goHome', 'На главную')}
        </button>
      </div>
    </section>
  )
}
