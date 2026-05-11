import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'

type Status = Awaited<ReturnType<typeof api.getMyArtist>>

export function ArtistProfileCard() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [status, setStatus] = useState<Status | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .getMyArtist()
      .then((r) => {
        if (!cancelled) setStatus(r)
      })
      .catch(() => {
        /* not fatal — card just stays hidden */
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!status) return null

  const a = status.artist
  const avatarUrl = a?.image_key
    ? `/api/v1/files/cover?key=${encodeURIComponent(a.image_key)}`
    : null

  // Completion: 6 fields incl. avatar.
  const filled = a
    ? [
        Boolean(a.image_key),
        (a.bio?.trim().length ?? 0) >= 20,
        !!a.country,
        !!a.birth_date,
        !!a.birthplace,
        !!a.website_url,
      ].filter(Boolean).length
    : 0
  const pct = a ? Math.round((filled / 6) * 100) : 0
  const needsAttention = status.has_artist && pct < 50

  return (
    <button
      type="button"
      className={`profile-artist-card${needsAttention ? ' profile-artist-card--attention' : ''}`}
      onClick={() => navigate('/profile/artist')}
    >
      <div className="profile-artist-card__avatar">
        {avatarUrl ? (
          <img src={avatarUrl} alt="" />
        ) : (
          <span className="profile-artist-card__avatar-fallback">
            {(a?.name ?? status.display_name ?? '?')
              .slice(0, 1)
              .toUpperCase()}
          </span>
        )}
      </div>
      <div className="profile-artist-card__body">
        <div className="profile-artist-card__title">
          {status.has_artist
            ? t('profileCard.artistTitle', 'Ваш профиль артиста')
            : t(
                'profileCard.becomeTitle',
                'Стать артистом на платформе',
              )}
        </div>
        <div className="profile-artist-card__subtitle">
          {status.has_artist
            ? needsAttention
              ? t(
                  'profileCard.artistNudge',
                  'Заполнено {{pct}}% — добавьте био и аватар',
                  { pct },
                )
              : t(
                  'profileCard.artistSubtitle',
                  'Имя: {{name}} · нажмите, чтобы редактировать',
                  { name: a?.name ?? '' },
                )
            : t(
                'profileCard.becomeSubtitle',
                'Имя артиста = ваш ник на платформе',
              )}
        </div>
        {status.has_artist ? (
          <div className="profile-artist-card__progress">
            <div
              className="profile-artist-card__progress-fill"
              style={{ width: `${pct}%` }}
            />
          </div>
        ) : null}
      </div>
      <span className="profile-artist-card__chev" aria-hidden>
        ›
      </span>
      <span className="visually-hidden">
        {t('profileCard.open', 'Открыть профиль артиста')}
      </span>
      {/* MotionPress is fine here too — keeping plain button for keyboard semantics + native focus ring */}
      <MotionPress
        type="button"
        variant="ghost"
        className="profile-artist-card__hidden-press"
        aria-hidden
        tabIndex={-1}
      />
    </button>
  )
}

export default ArtistProfileCard
