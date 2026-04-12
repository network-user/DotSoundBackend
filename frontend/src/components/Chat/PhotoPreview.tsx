import { useEffect, useRef, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'

const MAX_CAPTION = 1000
const MAX_FILE_MB = 10

interface Props {
  file: File
  onSend: (file: File, caption: string) => void
  onCancel: () => void
}

export function PhotoPreview({
  file,
  onSend,
  onCancel,
}: Props) {
  const [preview, setPreview] = useState('')
  const [caption, setCaption] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const sizeMb = file.size / 1024 / 1024
  const tooLarge = sizeMb > MAX_FILE_MB
  const captionOver = caption.length > MAX_CAPTION
  const canSend = !tooLarge && !captionOver

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleKeyDown = (
    e: React.KeyboardEvent,
  ) => {
    if (
      e.key === 'Enter' &&
      !e.shiftKey &&
      canSend
    ) {
      e.preventDefault()
      onSend(file, caption.trim())
    }
    if (e.key === 'Escape') onCancel()
  }

  return (
    <div className="photo-preview-overlay">
      <div className="photo-preview-panel scale-in">
        <div className="photo-preview-header">
          <button
            className="photo-preview-close"
            onClick={onCancel}
          >
            <Icon name="x" size={20} />
          </button>
          <span className="photo-preview-title">
            Отправить фото
          </span>
          <span className="photo-preview-size">
            {sizeMb.toFixed(1)} МБ
          </span>
        </div>

        <div className="photo-preview-image-wrap">
          {tooLarge && (
            <div className="photo-size-warning fade-in">
              <Icon name="info" size={18} />
              <span>
                Файл слишком большой (макс{' '}
                {MAX_FILE_MB} МБ)
              </span>
            </div>
          )}
          {preview ? (
            <img
              src={preview}
              alt=""
              className="photo-preview-image"
            />
          ) : (
            <div className="photo-preview-loading shimmer" />
          )}
        </div>

        <div className="photo-preview-footer">
          <div className="photo-caption-wrap">
            <input
              ref={inputRef}
              className="photo-preview-caption"
              value={caption}
              onChange={(e) =>
                setCaption(e.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Добавить подпись..."
              maxLength={MAX_CAPTION + 50}
            />
            {caption.length > MAX_CAPTION - 200 && (
              <span
                className={`char-counter ${captionOver ? 'over' : ''}`}
              >
                {caption.length}/{MAX_CAPTION}
              </span>
            )}
          </div>
          <button
            className="photo-preview-send"
            onClick={() =>
              onSend(file, caption.trim())
            }
            disabled={!canSend}
          >
            <Icon name="send" size={20} />
          </button>
        </div>
      </div>
    </div>
  )
}
