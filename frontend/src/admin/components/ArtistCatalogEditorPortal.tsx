import '@/styles/admin/redesign-admin.css'
import '../styles/admin.css'
import { StepUpProvider } from './auth/StepUpDialog'
import { AdminPromptProvider } from './layout/AdminPromptContext'
import { ArtistCatalogEditor } from './ArtistCatalogEditor'

export default function ArtistCatalogEditorPortal({
  artistId,
  artistName,
  open,
  onClose,
}: {
  artistId: number
  artistName: string
  open: boolean
  onClose: () => void
}) {
  return (
    <AdminPromptProvider>
      <StepUpProvider>
        <ArtistCatalogEditor
          artistId={artistId}
          artistName={artistName}
          open={open}
          onClose={onClose}
        />
      </StepUpProvider>
    </AdminPromptProvider>
  )
}
