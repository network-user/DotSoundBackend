import type { TFunction } from 'i18next'

export function lyricsTierAdminTitle(
  tier: string | null | undefined,
  t: TFunction,
): string {
  if (!tier) return '–'
  const key = `admin.tasks.lyricsTier.${tier}`
  const out = t(key)
  return out === key ? tier : out
}
