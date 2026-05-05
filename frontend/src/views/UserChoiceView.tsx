import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { UserChoicePlaylistResponse } from '@/types/api'

export function UserChoiceView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
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

  const handleShare = useCallback(async () => {
    const url = `${window.location.origin}${import.meta.env.BASE_URL}user-choice`
    try {
      if (navigator.share) {
        await navigator.share({
          title: t('userChoice.title'),
          text: t('userChoice.hint'),
          url,
        })
        return
      }
      await navigator.clipboard.writeText(url)
      toast.success('Ссылка скопирована')
    } catch {
      toast.error('Не удалось поделиться')
    }
  }, [t, toast])

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
        <button
          className="icon-btn"
          type="button"
          onClick={() => {
            void handleShare()
          }}
          aria-label="Поделиться"
        >
          <Icon name="share" size={18} />
        </button>
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage={t('userChoice.empty')}
      />
    </section>
  )
}
