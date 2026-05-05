import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { hapticNotification, hapticSelection } from '@/lib/telegram'
import { usePlayerActions } from '@/store/PlayerContext'
import { UploadFileTab } from '@/components/Upload/UploadFileTab'
import { UploadSoundCloudTab } from '@/components/Upload/UploadSoundCloudTab'
import { UploadYouTubeTab } from '@/components/Upload/UploadYouTubeTab'
import { UploadBandcampTab } from '@/components/Upload/UploadBandcampTab'
import type { Track } from '@/types/api'

type Tab = 'file' | 'soundcloud' | 'youtube' | 'bandcamp'

export function UploadView() {
  const navigate = useNavigate()
  const { playTrack } = usePlayerActions()
  const [tab, setTab] = useState<Tab>('file')

  const handleSuccess = async (track: Track) => {
    hapticNotification('success')
    navigate('/')
    await playTrack(track)
  }

  const handleTabChange = (next: Tab) => {
    if (tab === next) {
      return
    }
    hapticSelection()
    setTab(next)
  }

  return (
    <section id="view-upload" className="view active upload-view">
      <div className="view-header upload-view__header">
        <h2>Загрузка трека</h2>
        <p className="upload-view__subtitle">
          Добавь трек в библиотеку за пару шагов.
        </p>
      </div>

      <div className="upload-tabs">
        <button
          className={`upload-tab${tab === 'file' ? ' active' : ''}`}
          onClick={() => handleTabChange('file')}
        >
          Файл
        </button>
        <button
          className={`upload-tab${tab === 'soundcloud' ? ' active' : ''}`}
          onClick={() => handleTabChange('soundcloud')}
        >
          SoundCloud
        </button>
        <button
          className={`upload-tab${tab === 'youtube' ? ' active' : ''}`}
          onClick={() => handleTabChange('youtube')}
        >
          YouTube
        </button>
        <button
          className={`upload-tab${tab === 'bandcamp' ? ' active' : ''}`}
          onClick={() => handleTabChange('bandcamp')}
        >
          Bandcamp
        </button>
      </div>

      {tab === 'file' && <UploadFileTab onSuccess={handleSuccess} />}
      {tab === 'soundcloud' && <UploadSoundCloudTab onSuccess={handleSuccess} />}
      {tab === 'youtube' && <UploadYouTubeTab onSuccess={handleSuccess} />}
      {tab === 'bandcamp' && <UploadBandcampTab onSuccess={handleSuccess} />}
    </section>
  )
}
