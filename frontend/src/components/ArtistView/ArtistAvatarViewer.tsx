import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

interface Props {
  src: string
  alt: string
  onClose: () => void
}

export function ArtistAvatarViewer({
  src,
  alt,
  onClose,
}: Props) {
  const { t } = useTranslation()

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', handleKey)
      document.body.style.overflow = previousOverflow
    }
  }, [onClose])

  return (
    <div
      className="artist-avatar-viewer"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <MotionPress
        type="button"
        variant="icon"
        haptic="light"
        className="artist-avatar-viewer-close"
        ariaLabel={t('artist.avatar_close')}
        onClick={onClose}
      >
        <Icon name="x" size={20} />
      </MotionPress>
      <img
        src={src}
        alt={alt}
        className="artist-avatar-viewer-img"
      />
    </div>
  )
}
