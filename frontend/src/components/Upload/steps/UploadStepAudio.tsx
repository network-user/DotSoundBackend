import { type ChangeEvent, type DragEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { MorphIcon } from '@/components/ui/MorphIcon'

interface Props {
  audioFile: File | null
  audioDuration: number | null
  audioDragging: boolean
  onAudioFile: (file: File) => void
  onDragChange: (dragging: boolean) => void
}

function fmtDuration(sec: number | null): string {
  if (sec == null) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export function UploadStepAudio({
  audioFile,
  audioDuration,
  audioDragging,
  onAudioFile,
  onDragChange,
}: Props) {
  const { t } = useTranslation()

  const handleAudioChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onAudioFile(file)
  }

  return (
    <div className="form-group ru-up-step-audio">
      <label className="form-label">
        {t('redesign.upload.file.audioLabel')}
      </label>
      <div
        className={`audio-drop-zone ru-up-drop${audioDragging ? ' drag-over' : ''}`}
        onDragOver={(e: DragEvent) => {
          e.preventDefault()
          onDragChange(true)
        }}
        onDragEnter={(e: DragEvent) => {
          e.preventDefault()
          onDragChange(true)
        }}
        onDragLeave={() => onDragChange(false)}
        onDrop={(e: DragEvent) => {
          e.preventDefault()
          onDragChange(false)
          const file = e.dataTransfer.files[0]
          if (file) onAudioFile(file)
        }}
      >
        <span className="ru-up-drop__glyph" aria-hidden>
          <MorphIcon name="upload" size={28} />
        </span>
        <label className="file-pick-btn ru-up-drop__pick" htmlFor="audio-input">
          {t('redesign.upload.file.audioPick')}
        </label>
        <p className="file-name ru-up-drop__name">
          {audioFile
            ? audioFile.name
            : t('redesign.upload.file.audioDropHint')}
        </p>
        {audioFile && audioDuration !== null && (
          <p className="file-meta ru-up-drop__meta">
            {fmtDuration(audioDuration)}
          </p>
        )}
      </div>
      <input
        id="audio-input"
        type="file"
        accept="audio/*"
        hidden
        onChange={handleAudioChange}
      />
    </div>
  )
}
