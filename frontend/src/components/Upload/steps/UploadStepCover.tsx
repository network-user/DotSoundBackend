import { type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  coverPreview: string | null
  coverDragging: boolean
  onCoverFile: (file: File) => void
  onCoverClear: () => void
  onDragChange: (dragging: boolean) => void
}

export function UploadStepCover({
  coverPreview,
  coverDragging,
  onCoverFile,
  onCoverClear,
  onDragChange,
}: Props) {
  const { t } = useTranslation()

  const handleCoverChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onCoverFile(file)
    else onCoverClear()
  }

  return (
    <>
      <label
        className={`cover-picker ru-up-cover${coverDragging ? ' drag-over' : ''}`}
        htmlFor="cover-input"
        onDragOver={(e) => {
          e.preventDefault()
          onDragChange(true)
        }}
        onDragEnter={(e) => {
          e.preventDefault()
          onDragChange(true)
        }}
        onDragLeave={() => onDragChange(false)}
        onDrop={(e) => {
          e.preventDefault()
          onDragChange(false)
          const file = e.dataTransfer.files[0]
          if (file) onCoverFile(file)
        }}
      >
        <div className="cover-preview ru-up-cover__preview">
          {coverPreview ? (
            <img src={coverPreview} alt="" />
          ) : (
            <span className="cover-placeholder ru-up-cover__placeholder">
              <Icon name="image" size={40} />
            </span>
          )}
        </div>
        <span className="cover-label ru-up-cover__label">
          {t('redesign.upload.file.coverLabel')}
        </span>
      </label>
      <input
        id="cover-input"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={handleCoverChange}
      />
    </>
  )
}
