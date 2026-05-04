import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import ru from '@/locales/ru.json'
import en from '@/locales/en.json'
import ruX1 from '@/locales/i18n_extra_ru.json'
import enX1 from '@/locales/i18n_extra_en.json'
import ruX2 from '@/locales/i18n_extra2_ru.json'
import enX2 from '@/locales/i18n_extra2_en.json'

type JsonObj = Record<string, unknown>
const BRAND_RU = '.\u0437\u0432\u0443\u043a'

function isPlainObject(
  v: unknown,
): v is JsonObj {
  return (
    v !== null && typeof v === 'object' && !Array.isArray(v)
  )
}

function deepMerge(
  base: JsonObj,
  ext: JsonObj,
): JsonObj {
  const out: JsonObj = { ...base }
  for (const k of Object.keys(ext)) {
    const b = out[k]
    const e = ext[k]
    if (isPlainObject(b) && isPlainObject(e)) {
      out[k] = deepMerge(b, e)
    } else {
      out[k] = e
    }
  }
  return out
}

function localizeRuBrand(v: unknown): unknown {
  if (typeof v === 'string') {
    return v.split('.sound').join(BRAND_RU)
  }
  if (Array.isArray(v)) {
    return v.map(localizeRuBrand)
  }
  if (isPlainObject(v)) {
    const out: JsonObj = {}
    for (const k of Object.keys(v)) {
      out[k] = localizeRuBrand(v[k])
    }
    return out
  }
  return v
}

const enT = deepMerge(
  deepMerge(
    en as unknown as JsonObj,
    enX1 as unknown as JsonObj,
  ),
  enX2 as unknown as JsonObj,
)
const ruMerged = deepMerge(
  deepMerge(
    ru as unknown as JsonObj,
    ruX1 as unknown as JsonObj,
  ),
  ruX2 as unknown as JsonObj,
)
const ruT = localizeRuBrand(ruMerged) as JsonObj

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
      en: { translation: enT },
      ru: { translation: ruT },
    },
    fallbackLng: 'ru',
    detection: {
      order: [
        'telegramDetector',
        'localStorage',
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
