import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePlayer } from '@/store/PlayerContext'
import { UploadFileTab } from '@/components/Upload/UploadFileTab'
import { UploadSoundCloudTab } from '@/components/Upload/UploadSoundCloudTab'
import { UploadYouTubeTab } from '@/components/Upload/UploadYouTubeTab'
import { UploadBandcampTab } from '@/components/Upload/UploadBandcampTab'
import type { Track } from '@/types/api'

type Tab = 'file' | 'soundcloud' | 'youtube' | 'bandcamp'

export function UploadView() {
  const navigate = useNavigate()
  const { playTrack } = usePlayer()
  const [tab, setTab] = useState<Tab>('file')

  const handleSuccess = async (track: Track) => {
    navigate('/')
    await playTrack(track)
  }

  return (
    <section id="view-upload" className="view active">
      <div className="view-header"><h2>Загрузить трек</h2></div>

      <div className="upload-tabs">
        <button
          className={`upload-tab${tab === 'file' ? ' active' : ''}`}
          onClick={() => setTab('file')}
        >
          Файл
        </button>
        <button
          className={`upload-tab${tab === 'soundcloud' ? ' active' : ''}`}
          onClick={() => setTab('soundcloud')}
        >
          SoundCloud
        </button>
        <button
          className={`upload-tab${tab === 'youtube' ? ' active' : ''}`}
          onClick={() => setTab('youtube')}
        >
          YouTube
        </button>
        <button
          className={`upload-tab${tab === 'bandcamp' ? ' active' : ''}`}
          onClick={() => setTab('bandcamp')}
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
