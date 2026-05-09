import { useEffect, useState } from 'react'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'

const STORAGE_KEY = 'cookie_notice_dismissed'
const STORAGE_VALUE = 'v1'

/**
 * Non-blocking уведомление об использовании cookies / localStorage.
 *
 * Показывается **один раз** при первой загрузке Mini App и в обычном
 * браузере. Закрывается одной кнопкой; флаг `cookie_notice_dismissed`
 * сохраняется в localStorage. Не модальный — поверх контента
 * прилипает к нижнему краю, контенту не мешает.
 *
 * 152-ФЗ: явное уведомление об обработке (имена ПДн ключей и
 * подпроцессоры — в `/legal/privacy`).
 */
export function CookieNotice() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    try {
      if (
        typeof window !== 'undefined' &&
        window.localStorage.getItem(STORAGE_KEY) !==
          STORAGE_VALUE
      ) {
        setVisible(true)
      }
    } catch {
      // localStorage недоступен (private mode, ITP) — показываем
      // баннер каждый раз, что соответствует «не скрывать
      // обработку без подтверждения».
      setVisible(true)
    }
  }, [])

  if (!visible) return null

  const dismiss = () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, STORAGE_VALUE)
    } catch {
      // ignore
    }
    setVisible(false)
  }

  return (
    <div
      className="cookie-notice"
      role="region"
      aria-label="Уведомление об обработке данных"
    >
      <div className="cookie-notice__inner">
        <Icon
          name="info"
          size={18}
          className="cookie-notice__icon"
          aria-hidden="true"
        />
        <p className="cookie-notice__text">
          DotSound использует localStorage и cookies, необходимые
          для работы сервиса (авторизация, настройки плеера, тема).
          Рекламные и аналитические трекеры третьих лиц не
          используются. Подробнее —{' '}
          <a
            href={`${import.meta.env.BASE_URL}legal/privacy`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Политика конфиденциальности
          </a>
          .
        </p>
        <MotionPress
          variant="primary"
          haptic="selection"
          className="cookie-notice__btn"
          onClick={dismiss}
        >
          Понятно
        </MotionPress>
      </div>
    </div>
  )
}
