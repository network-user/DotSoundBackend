import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import ru from '@/locales/ru.json'
import en from '@/locales/en.json'

function getTelegramLanguage(): string | undefined {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tg = (window as any)?.Telegram?.WebApp
    return tg?.initDataUnsafe?.user?.language_code
  } catch {
    return undefined
  }
}

const customDetector = {
  name: 'telegramDetector',
  lookup(): string | undefined {
    return getTelegramLanguage()
  },
}

const detector = new LanguageDetector()
detector.addDetector(customDetector)

i18n
  .use(detector)
  .use(initReactI18next)
  .init({
    resources: {
      ru: { translation: ru },
      en: { translation: en },
    },
    fallbackLng: 'ru',
    detection: {
      order: [
        'localStorage',
        'telegramDetector',
        'navigator',
      ],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },
    interpolation: {
      escapeValue: false,
    },
  })

export default i18n
