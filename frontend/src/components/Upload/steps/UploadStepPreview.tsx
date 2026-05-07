import { useTranslation } from 'react-i18next'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  title: string
  artistLabel: string
  audioDuration: number | null
  coverPreview: string | null
}

function fmtDuration(sec: number | null): string {
  if (sec == null) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export function UploadStepPreview({
  title,
  artistLabel,
  audioDuration,
  coverPreview,
}: Props) {
  const { t } = useTranslation()
  const missing = t('redesign.upload.file.previewMissing')
  return (
    <div className="ru-up-preview-stage">
      <AmbientStage coverUrl={coverPreview}>
        <div className="ru-up-preview-stage__inner">
          <div className="ru-up-preview-cover-wrap">
            {coverPreview ? (
              <KenBurnsCover
                src={coverPreview}
                alt={t('redesign.upload.ambientAlt')}
              />
            ) : (
              <div className="ru-up-preview-placeholder">
                <Icon name="music" size={44} />
              </div>
            )}
          </div>
          <div className="ru-up-preview-meta">
            <strong>{title.trim() || missing}</strong>
            <span>{artistLabel.trim() || missing}</span>
            {audioDuration !== null && (
              <span>{fmtDuration(audioDuration)}</span>
            )}
          </div>
        </div>
      </AmbientStage>
    </div>
  )
}
