import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

export function getBrandLabelForLanguage(
  language?: string | null,
): string {
  return (language ?? '')
    .toLowerCase()
    .startsWith('ru')
    ? '.\u0437\u0432\u0443\u043a'
    : '.sound'
}

export function useBrandLabel(): string {
  const { i18n } = useTranslation()
  return useMemo(
    () =>
      getBrandLabelForLanguage(
        i18n.resolvedLanguage ?? i18n.language,
      ),
    [i18n.language, i18n.resolvedLanguage],
  )
}
