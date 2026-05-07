import { api } from '@/lib/api'
import type { Track } from '@/types/api'
import { UrlImportTab } from './UrlImportTab'

interface Props {
  onSuccess: (track: Track) => void
}

export function UploadBandcampTab({ onSuccess }: Props) {
  return (
    <UrlImportTab
      source={{
        id: 'Bandcamp',
        iconName: 'source-bandcamp',
        placeholder: 'https://artist.bandcamp.com/track/track-name',
        importFn: api.importBandcampTrack,
        errorKey: 'bandcamp',
      }}
      onSuccess={onSuccess}
    />
  )
}
