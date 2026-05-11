import { useTranslation } from 'react-i18next'

import { MotionPress } from '@/components/ui/MotionPress'

interface DuplicateModalProps {
  filename: string
  existingTitle: string | null
  existingTrackId: number
  uploadedAt: string | null
  onOpen: (trackId: number) => void
  onUploadAnyway: () => void
  onCancel: () => void
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  } catch {
    return ''
  }
}

export function DuplicateModal({
  filename,
  existingTitle,
  existingTrackId,
  uploadedAt,
  onOpen,
  onUploadAnyway,
  onCancel,
}: DuplicateModalProps) {
  const { t } = useTranslation()
  const date = formatDate(uploadedAt)
  return (
    <div
      className="dlg-dupe-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dlg-dupe-title"
    >
      <div className="dlg-dupe">
        <h3 id="dlg-dupe-title">
          {t('upload.dupe.title', 'Этот трек уже у тебя есть')}
        </h3>
        <p>
          {t(
            'upload.dupe.body',
            'Файл «{{file}}» совпадает с треком «{{title}}»{{when}}. Что сделать?',
            {
              file: filename,
              title: existingTitle ?? '—',
              when: date ? `, загружен ${date}` : '',
            },
          )}
        </p>
        <div className="dlg-dupe__actions">
          <MotionPress
            type="button"
            variant="primary"
            onClick={() => onOpen(existingTrackId)}
          >
            {t('upload.dupe.open', 'Открыть существующий')}
          </MotionPress>
          <MotionPress
            type="button"
            variant="ghost"
            onClick={onUploadAnyway}
          >
            {t('upload.dupe.uploadAnyway', 'Загрузить как копию')}
          </MotionPress>
          <MotionPress
            type="button"
            variant="ghost"
            onClick={onCancel}
          >
            {t('common.cancel', 'Отмена')}
          </MotionPress>
        </div>
      </div>
    </div>
  )
}

export default DuplicateModal
