import { api } from '@/lib/api'
import type { Track } from '@/types/api'
import { UrlImportTab } from './UrlImportTab'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadYouTubeTab({ onSuccess }: Props) {
  return (
    <UrlImportTab
      source={{
        id: 'YouTube',
        iconName: 'source-youtube',
        placeholder: 'https://www.youtube.com/watch?v=...',
        importFn: api.importYouTubeTrack,
        errorKey: 'youtube',
      }}
      onSuccess={onSuccess}
    />
  )
}
