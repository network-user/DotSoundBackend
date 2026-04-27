import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import type { UserChoicePlaylistResponse } from '@/types/api'

export function UserChoiceView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [data, setData] = useState<
    UserChoicePlaylistResponse | null
  >(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    api
      .getUserChoicePlaylist(100)
      .then(setData)
      .catch(() =>
        setData({
          tracks: [],
          generated_at: '',
          score_version: '',
        }),
      )
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const tracks = loading
    ? null
    : (data?.tracks ?? [])

  return (
    <section className="view active">
      <div className="view-header">
        <button
          className="icon-btn"
          type="button"
          onClick={() => navigate(-1)}
        >
          <Icon
            name="chevron"
            size={20}
            className="back-chevron"
          />
        </button>
        <div style={{ flex: 1 }}>
          <h2>{t('userChoice.title')}</h2>
          <span className="hint">
            {t('userChoice.hint')}
          </span>
        </div>
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage={t('userChoice.empty')}
      />
    </section>
  )
}
