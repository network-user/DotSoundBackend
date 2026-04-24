import type { TFunction } from 'i18next'

import type { AppNotification } from '@/types/api'

const SOURCE_KEY_BY_ID: Record<string, string> = {
  telegram: 'telegram',
  yandex_music: 'yandexMusic',
  vk_music: 'vkMusic',
  spotify: 'spotify',
  soundcloud_playlist: 'soundcloud',
}

const COMPLAINT_TYPE_SUFFIX: Record<string, string> = {
  complaint_resolved: 'resolved',
  complaint_dismissed: 'dismissed',
  complaint_in_progress: 'inProgress',
}

function sourceLabel(source: string, t: TFunction): string {
  if (!source) return ''
  const k = SOURCE_KEY_BY_ID[source]
  if (k) {
    return t(`notifications.import.sources.${k}`)
  }
  return source
}

function toNum(v: unknown): number {
  if (typeof v === 'number' && !Number.isNaN(v)) return v
  const n = parseInt(String(v ?? 0), 10)
  return Number.isNaN(n) ? 0 : n
}

/** Resolves in-app and WS notification text using the active UI language. */
export function resolveNotificationText(
  n: Pick<
    AppNotification,
    'type' | 'title' | 'body' | 'data'
  >,
  t: TFunction,
): { title: string; body: string } {
  const { type, title, body, data } = n
  const d = data
  if (!d || typeof d !== 'object') {
    return { title, body }
  }
  const sl = sourceLabel(
    String((d as Record<string, unknown>).source ?? ''),
    t,
  )

  if (type === 'import_failed') {
    const fail = toNum(
      (d as Record<string, unknown>).failed,
    )
    return {
      title: t('notifications.import.failedTitle'),
      body: t('notifications.import.failedBody', {
        source: sl,
        count: fail,
      }),
    }
  }

  if (type === 'import_completed') {
    const done = toNum(
      (d as Record<string, unknown>).completed,
    )
    const fail = toNum(
      (d as Record<string, unknown>).failed,
    )
    const tot = toNum(
      (d as Record<string, unknown>).total,
    )
    if (done === 0 && fail === 0 && tot === 0) {
      return {
        title: t('notifications.import.completeTitle'),
        body: t('notifications.import.emptyBody', {
          source: sl,
        }),
      }
    }
    if (fail > 0) {
      return {
        title: t('notifications.import.completeTitle'),
        body: t('notifications.import.partialBody', {
          source: sl,
          done,
          fail,
        }),
      }
    }
    return {
      title: t('notifications.import.completeTitle'),
      body: t('notifications.import.addedBody', {
        source: sl,
        count: done,
      }),
    }
  }

  const suffix = COMPLAINT_TYPE_SUFFIX[type]
  if (suffix) {
    return {
      title: t(`notifications.complaint.${suffix}.title`),
      body: t(`notifications.complaint.${suffix}.body`),
    }
  }

  return { title, body }
}

export function buildNotificationToastMessage(
  n: Pick<
    AppNotification,
    'type' | 'title' | 'body' | 'data'
  >,
  t: TFunction,
): string {
  const { title, body } = resolveNotificationText(n, t)
  const ti = title.trim()
  const bi = body.trim()
  if (ti && bi) {
    return `${ti}\n${bi}`
  }
  return bi || ti
}
