import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

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

async function loadLocaleBundle(
  lang: 'ru' | 'en',
): Promise<JsonObj> {
  if (lang === 'ru') {
    const [base, x1, x2] = await Promise.all([
      import('@/locales/ru.json'),
      import('@/locales/i18n_extra_ru.json'),
      import('@/locales/i18n_extra2_ru.json'),
    ])
    const merged = deepMerge(
      deepMerge(
        base.default as unknown as JsonObj,
        x1.default as unknown as JsonObj,
      ),
      x2.default as unknown as JsonObj,
    )
    return localizeRuBrand(merged) as JsonObj
  }
  const [base, x1, x2] = await Promise.all([
    import('@/locales/en.json'),
    import('@/locales/i18n_extra_en.json'),
    import('@/locales/i18n_extra2_en.json'),
  ])
  return deepMerge(
    deepMerge(
      base.default as unknown as JsonObj,
      x1.default as unknown as JsonObj,
    ),
    x2.default as unknown as JsonObj,
  )
}

const loadedLocales = new Set<string>()

async function ensureLocale(lang: string): Promise<void> {
  const normalized = lang.toLowerCase().startsWith('ru')
    ? 'ru'
    : 'en'
  if (loadedLocales.has(normalized)) return
  const bundle = await loadLocaleBundle(normalized)
  i18n.addResourceBundle(
    normalized,
    'translation',
    bundle,
    true,
    true,
  )
  loadedLocales.add(normalized)
}

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

function detectInitialLanguage(): 'ru' | 'en' {
  try {
    const tg = getTelegramLanguage()
    if (tg) return tg.toLowerCase().startsWith('ru') ? 'ru' : 'en'
    const stored = localStorage.getItem('i18nextLng')
    if (stored)
      return stored.toLowerCase().startsWith('ru') ? 'ru' : 'en'
    const nav = navigator.language
    if (nav)
      return nav.toLowerCase().startsWith('ru') ? 'ru' : 'en'
  } catch {
    /* ignore */
  }
  return 'ru'
}

const initialLang = detectInitialLanguage()

export const i18nReady: Promise<typeof i18n> =
  loadLocaleBundle(initialLang).then(async (bundle) => {
    loadedLocales.add(initialLang)
    await i18n
      .use(detector)
      .use(initReactI18next)
      .init({
        resources: {
          [initialLang]: { translation: bundle },
        },
        fallbackLng: initialLang,
        lng: initialLang,
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
    i18n.on('languageChanged', (lng) => {
      void ensureLocale(lng)
    })
    return i18n
  })

export default i18n
