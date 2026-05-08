import type { TFunction } from 'i18next'
import type { Track } from '@/types/api'

export function fmtTrackDuration(sec: number | null): string {
  if (sec == null || sec <= 0) return ''
  const mins = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${mins}:${s}`
}

export function formatTrackCardWhen(iso: string): string {
  const d = new Date(iso)
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

export function getTrackSourceLabel(track: Track, t: TFunction): string {
  const raw = track.source_name?.trim()
  if (raw) {
    return raw.length > 36 ? `${raw.slice(0, 33)}…` : raw
  }
  switch (track.source) {
    case 'soundcloud':
      return 'SoundCloud'
    case 'youtube':
      return 'YouTube'
    case 'bandcamp':
      return 'Bandcamp'
    case 'telegram':
      return t('trackCard.sourceTelegram', 'Telegram')
    case 'internal':
      if (track.catalog_type === 'ugc') {
        return t('trackCard.sourceUpload', 'Upload')
      }
      if (track.catalog_type === 'licensed') {
        return t(
          'trackCard.sourceLicensedShort',
          'Licensed',
        )
      }
      return t('trackCard.sourcePlatform', 'DotSound')
    default:
      return String(track.source)
  }
}

type TrackWithSocial = Track & {
  liked_at?: string
  disliked_at?: string
}

export function getTrackContextTimeText(
  track: Track,
  t: TFunction,
): string | null {
  if (track.last_listen_at) {
    const when = formatTrackCardWhen(track.last_listen_at)
    const dur = fmtTrackDuration(
      track.last_listen_seconds ?? null,
    )
    if (dur) {
      return t('redesign.library.historyWhenAndDur', {
        when,
        duration: dur,
      })
    }
    return t('redesign.library.historyWhenOnly', { when })
  }
  const st = track as TrackWithSocial
  if (st.liked_at) {
    return t('trackCard.addedAt', {
      when: formatTrackCardWhen(st.liked_at),
    })
  }
  if (st.disliked_at) {
    return t('trackCard.dislikedAt', {
      when: formatTrackCardWhen(st.disliked_at),
    })
  }
  return null
}

export function buildTrackCardSummaryLine(
  track: Track,
  t: TFunction,
  suffix?: string | null,
): string {
  const parts: string[] = []
  const dur = fmtTrackDuration(track.duration_seconds)
  if (dur) parts.push(dur)
  parts.push(getTrackSourceLabel(track, t))
  const ctx = getTrackContextTimeText(track, t)
  if (ctx) parts.push(ctx)
  const base = parts.join(' · ')
  const extra = suffix?.trim()
  if (extra) return `${base} · ${extra}`
  return base
}
