import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

interface HomeSection {
  title: string
  section_type: string
  tracks: Track[]
}

export function HomeView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [sections, setSections] = useState<HomeSection[] | null>(null)
  const [fallbackTracks, setFallbackTracks] = useState<Track[] | null>(null)

  useEffect(() => {
    setSections(null)
    api.getHomeRecommendations()
      .then((data) => {
        setSections(data.sections)
      })
      .catch(() => {
        api.getTracks({ size: 50 })
          .then((data) => setFallbackTracks(data.items))
          .catch(() => setFallbackTracks([]))
      })
  }, [])

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
        className="playlist-card"
        style={{ margin: '8px 16px 4px', width: 'calc(100% - 32px)' }}
        onClick={() => navigate('/daily-mix')}
      >
        <div style={{ fontSize: 32, lineHeight: 1 }}>📅</div>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>Плейлист дня</div>
          <div className="hint" style={{ fontSize: 12 }}>Персональная подборка + открытия</div>
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
        <TrackList tracks={fallbackTracks} emptyMessage={t('home.empty')} />
      )}
    </section>
  )
}
