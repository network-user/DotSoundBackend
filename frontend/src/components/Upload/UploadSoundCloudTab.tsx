import { api } from '@/lib/api'
import type { Track } from '@/types/api'
import { UrlImportTab } from './UrlImportTab'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadSoundCloudTab({ onSuccess }: Props) {
  return (
    <UrlImportTab
      source={{
        id: 'SoundCloud',
        iconName: 'source-soundcloud',
        placeholder: 'https://soundcloud.com/artist/track',
        importFn: api.importSCTrack,
        errorKey: 'soundcloud',
      }}
      onSuccess={onSuccess}
    />
  )
}
