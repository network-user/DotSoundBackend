import {
  LEGAL_VERSION,
  LEGAL_VERSION_DATE,
  LEGAL_OPERATOR,
  LEGAL_CONTACT_EMAIL,
} from '@/views/legalContent'

const LEGAL_BASE = `${import.meta.env.BASE_URL}legal/`

/**
 * Юридическая секция в настройках профиля.
 *
 * Не блокирует UI и не запрашивает повторный акцепт — пользователь
 * уже принял условия неявно при онбординге. Здесь показывается:
 *   - принятая версия пакета документов;
 *   - бейдж 18+;
 *   - оператор и контакт;
 *   - быстрые ссылки на все документы;
 *   - почтовый адрес для запросов прав субъекта (152-ФЗ ст. 14).
 *
 * Кнопку «Удалить аккаунт» сюда не дублируем — она в
 * `AccountDangerZone` ниже по странице.
 *
 * Ссылки используют `import.meta.env.BASE_URL`, чтобы корректно
 * работать при Vite-сборке с `base: '/mini_app/'` — иначе при
 * `target="_blank"` браузер открыл бы корень домена без префикса.
 */
export function SettingsLegalSection() {
  return (
    <section className="settings-legal-section">
      <h3>Юридическая информация</h3>
      <p className="settings-legal-section__meta">
        <span>18+</span>
        Версия пакета документов: {LEGAL_VERSION} от{' '}
        {LEGAL_VERSION_DATE}. Оператор обработки персональных
        данных — {LEGAL_OPERATOR}.
      </p>
      <div className="settings-legal-section__links">
        <a
          href={`${LEGAL_BASE}terms`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Условия
        </a>
        <a
          href={`${LEGAL_BASE}privacy`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Политика конфиденциальности
        </a>
        <a
          href={`${LEGAL_BASE}anti-abuse-signals`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Сигналы против автоматических регистраций
        </a>
        <a
          href={`${LEGAL_BASE}copyright`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Авторские права
        </a>
        <a
          href={`${LEGAL_BASE}upload-rules`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Правила загрузки
        </a>
        <a
          href={`${LEGAL_BASE}rightsholders`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Правообладателям
        </a>
      </div>
      <p className="settings-legal-section__meta">
        Запросы по обработке персональных данных и удалению —
        напишите на{' '}
        <a
          href={`mailto:${LEGAL_CONTACT_EMAIL}?subject=DotSound%20%E2%80%94%20%D0%B7%D0%B0%D0%BF%D1%80%D0%BE%D1%81%20%D0%BF%D0%BE%20%D0%9F%D0%94%D0%BD`}
        >
          {LEGAL_CONTACT_EMAIL}
        </a>
        . Срок ответа — до 30 дней.
      </p>
    </section>
  )
}
