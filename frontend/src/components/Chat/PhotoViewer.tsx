import {
  useEffect,
  useRef,
  useState,
} from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  src: string
  onClose: () => void
}

const MIN_SCALE = 1
const MAX_SCALE = 3
const SCALE_STEP = 0.25

export function PhotoViewer({ src, onClose }: Props) {
  const [scale, setScale] = useState(1)
  const [status, setStatus] = useState<
    string | null
  >(null)
  const tapStartRef = useRef<{
    x: number
    y: number
  } | null>(null)
  const statusTimerRef = useRef<
    ReturnType<typeof setTimeout> | null
  >(null)

  const setStatusMessage = (value: string) => {
    setStatus(value)
    if (statusTimerRef.current) {
      clearTimeout(statusTimerRef.current)
    }
    statusTimerRef.current = setTimeout(() => {
      setStatus(null)
      statusTimerRef.current = null
    }, 1800)
  }

  const clampScale = (value: number) =>
    Math.min(
      MAX_SCALE,
      Math.max(MIN_SCALE, value),
    )

  const zoomIn = () => {
    setScale((current) =>
      clampScale(current + SCALE_STEP),
    )
  }

  const zoomOut = () => {
    setScale((current) =>
      clampScale(current - SCALE_STEP),
    )
  }

  const resolveFileName = () => {
    try {
      const url = new URL(
        src,
        window.location.origin,
      )
      const name = url.pathname.split('/').pop()
      if (name) return name
    } catch {}
    return 'image'
  }

  const loadBlob = async () => {
    const response = await fetch(src)
    if (!response.ok) {
      throw new Error('load_failed')
    }
    return response.blob()
  }

  const handleDownload = async () => {
    try {
      const blob = await loadBlob()
      const objectUrl =
        URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = resolveFileName()
      link.click()
      URL.revokeObjectURL(objectUrl)
      setStatusMessage('Сохранено')
    } catch {
      setStatusMessage(
        'Не удалось сохранить',
      )
    }
  }

  const handleCopy = async () => {
    if (
      !navigator.clipboard?.write ||
      typeof ClipboardItem === 'undefined'
    ) {
      setStatusMessage(
        'Буфер обмена недоступен',
      )
      return
    }
    try {
      const blob = await loadBlob()
      await navigator.clipboard.write([
        new ClipboardItem({
          [blob.type || 'image/png']: blob,
        }),
      ])
      setStatusMessage('Скопировано')
    } catch {
      setStatusMessage(
        'Не удалось скопировать',
      )
    }
  }

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === '+' || e.key === '=') {
        zoomIn()
      }
      if (e.key === '-') {
        zoomOut()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => {
      if (statusTimerRef.current) {
        clearTimeout(statusTimerRef.current)
      }
      window.removeEventListener(
        'keydown',
        handleKey,
      )
    }
  }, [onClose])

  return (
    <div
      className="photo-viewer-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        className="photo-viewer-shell"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="photo-viewer-toolbar">
          <div className="photo-viewer-toolbar-group">
            <button
              className="photo-viewer-action"
              onClick={zoomOut}
              disabled={scale <= MIN_SCALE}
            >
              <Icon name="minus" size={18} />
            </button>
            <span className="photo-viewer-zoom-label">
              {Math.round(scale * 100)}%
            </span>
            <button
              className="photo-viewer-action"
              onClick={zoomIn}
              disabled={scale >= MAX_SCALE}
            >
              <Icon name="plus" size={18} />
            </button>
          </div>
          <div className="photo-viewer-toolbar-group">
            <button
              className="photo-viewer-action"
              onClick={() => {
                void handleCopy()
              }}
            >
              <Icon name="copy" size={18} />
            </button>
            <button
              className="photo-viewer-action"
              onClick={() => {
                void handleDownload()
              }}
            >
              <Icon name="download" size={18} />
            </button>
            <button
              className="photo-viewer-action"
              onClick={onClose}
            >
              <Icon name="x" size={20} />
            </button>
          </div>
        </div>
        <div className="photo-viewer-stage">
          <div
            className="photo-viewer-image-wrap"
            onWheel={(e) => {
              e.preventDefault()
              if (e.deltaY < 0) {
                zoomIn()
                return
              }
              zoomOut()
            }}
          >
            <img
              src={src}
              alt=""
              className="photo-viewer-img"
              style={{
                transform: `scale(${scale})`,
              }}
              onPointerDown={(e) => {
                tapStartRef.current = {
                  x: e.clientX,
                  y: e.clientY,
                }
              }}
              onPointerUp={(e) => {
                if (scale > MIN_SCALE) return
                const start = tapStartRef.current
                tapStartRef.current = null
                if (!start) return
                const dx = Math.abs(
                  e.clientX - start.x,
                )
                const dy = Math.abs(
                  e.clientY - start.y,
                )
                if (dx <= 8 && dy <= 8) {
                  onClose()
                }
              }}
              onPointerCancel={() => {
                tapStartRef.current = null
              }}
            />
          </div>
          {status && (
            <div className="photo-viewer-status">
              {status}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
