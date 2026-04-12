import { useEffect } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  src: string
  onClose: () => void
}

export function PhotoViewer({ src, onClose }: Props) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () =>
      window.removeEventListener(
        'keydown',
        handleKey,
      )
  }, [onClose])

  return (
    <div
      className="photo-viewer-overlay"
      onClick={onClose}
    >
      <button
        className="photo-viewer-close"
        onClick={onClose}
      >
        <Icon name="x" size={24} />
      </button>
      <img
        src={src}
        alt=""
        className="photo-viewer-img"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  )
}
