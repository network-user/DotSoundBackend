import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { coverProxyUrl } from '@/lib/coverProxy'
import { api } from '@/lib/api'

type Status = Awaited<ReturnType<typeof api.getMyArtist>>

export function ProfileArtistPreview() {
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
        /* swallow — show nothing if endpoint fails */
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!status) return null

  const a = status.artist
  const avatarUrl = a?.image_key
    ? coverProxyUrl(a.image_key)
    : null

  return (
    <div className="ru-up-artist-preview">
      <div className="ru-up-artist-preview__avatar">
        {avatarUrl ? (
          <img src={avatarUrl} alt="" />
        ) : (
          <span>
            {(a?.name ?? status.display_name ?? '?')
              .slice(0, 1)
              .toUpperCase()}
          </span>
        )}
      </div>
      <div className="ru-up-artist-preview__meta">
        <div className="ru-up-artist-preview__name">
          {a?.name ?? status.display_name}
        </div>
        <div className="ru-up-artist-preview__sub">
          {status.has_artist
            ? t(
                'uploadArtistPreview.exists',
                'Трек будет привязан к вашему профилю артиста',
              )
            : t(
                'uploadArtistPreview.willCreate',
                'Профиль артиста будет создан автоматически',
              )}
        </div>
      </div>
      <button
        type="button"
        className="ru-up-artist-preview__edit"
        onClick={(e) => {
          e.preventDefault()
          navigate('/profile/artist')
        }}
      >
        {t('uploadArtistPreview.edit', 'Изменить')}
      </button>
    </div>
  )
}

export default ProfileArtistPreview
