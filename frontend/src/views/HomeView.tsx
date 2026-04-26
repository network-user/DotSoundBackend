import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useToast } from '@/components/ui/Toast'
import { TrackList } from '@/components/TrackList/TrackList'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { Icon } from '@/components/Icon/Icon'
import { api, getApiErrorMessage } from '@/lib/api'
import { firstTrackFromDailyPlaylist } from '@/lib/playlistFirstTrack'
import { usePlayerActions } from '@/store/PlayerContext'
import type { Track } from '@/types/api'

interface HomeSection {
  title: string
  section_type: string
  tracks: Track[]
}

export function HomeView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const { playTrack } = usePlayerActions()
  const [sections, setSections] = useState<HomeSection[] | null>(null)
  const [fallbackTracks, setFallbackTracks] = useState<
    Track[] | null
  >(null)
  const [playLoading, setPlayLoading] = useState(false)

  useEffect(() => {
    setSections(null)
    api
      .getHomeRecommendations()
      .then((data) => {
        setSections(data.sections)
      })
      .catch(() => {
        api
          .getTracks({ size: 50 })
          .then((data) => setFallbackTracks(data.items))
          .catch(() => setFallbackTracks([]))
      })
  }, [])

  const handlePlayFromDaily = useCallback(async () => {
    setPlayLoading(true)
    try {
      const d = await api.getDailyPlaylist()
      const first = firstTrackFromDailyPlaylist(d)
      if (!first) {
        toast.error(t('home.playEmpty'))
        return
      }
      await playTrack(first)
    } catch (e) {
      toast.error(
        getApiErrorMessage(
          e,
          t('home.playError'),
        ),
      )
    } finally {
      setPlayLoading(false)
    }
  }, [playTrack, t, toast])

  return (
    <section id="view-home" className="view active">
      <div className="view-header view-header-row">
        <div>
          <h2>{t('home.title')}</h2>
          <span className="hint">{t('home.tagline')}</span>
        </div>
        <NotificationBell />
      </div>

      <button
        type="button"
        className="home-radio-play"
        disabled={playLoading}
        onClick={handlePlayFromDaily}
        aria-label={t('home.playRadioAria')}
      >
        <span className="home-radio-play__icon" aria-hidden>
          <Icon name="play" size={28} />
        </span>
        <span className="home-radio-play__text">
          <span className="home-radio-play__title">
            {t('home.playRadio')}
          </span>
          <span className="hint home-radio-play__hint">
            {t('home.playRadioHint')}
          </span>
        </span>
      </button>

      <button
        className="playlist-card"
        style={{ margin: '0 16px 4px', width: 'calc(100% - 32px)' }}
        onClick={() => navigate('/daily-mix')}
      >
        <div className="playlist-cover" aria-hidden>
          <Icon name="calendar" size={26} />
        </div>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>
            {t('home.dayPlaylistTitle')}
          </div>
          <div
            className="hint"
            style={{ fontSize: 12 }}
          >
            {t('home.dayPlaylistHint')}
          </div>
        </div>
        <Icon name="chevron" size={18} className="text-secondary" />
      </button>

      <button
        className="playlist-card"
        style={{ margin: '8px 16px 4px', width: 'calc(100% - 32px)' }}
        onClick={() => navigate('/weekly-mix')}
      >
        <div className="playlist-cover" aria-hidden>
          <Icon name="star" size={26} />
        </div>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>
            {t('home.weekPlaylistTitle')}
          </div>
          <div
            className="hint"
            style={{ fontSize: 12 }}
          >
            {t('home.weekPlaylistHint')}
          </div>
        </div>
        <Icon name="chevron" size={18} className="text-secondary" />
      </button>

      {sections === null && fallbackTracks === null && (
        <div className="loader" />
      )}

      {sections && sections.map((section, i) => (
        <div key={`${section.section_type}-${i}`} className="home-section">
          <h3 className="home-section-title">{section.title}</h3>
          <TrackList
            tracks={section.tracks}
            emptyMessage={t('home.empty')}
          />
        </div>
      ))}

      {sections && sections.length === 0 && (
        <TrackList tracks={[]} emptyMessage={t('home.empty')} />
      )}

      {!sections && fallbackTracks !== null && (
        <TrackList
          tracks={fallbackTracks}
          emptyMessage={t('home.empty')}
        />
      )}
    </section>
  )
}
