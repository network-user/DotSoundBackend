import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

interface Props {
  initials: string
  defaultUrl: string | null
  hasCustomAvatar: boolean
  onUploaded?: (url: string) => void
  onResetToDefault?: () => void
}

const SEED_GRADIENTS: ReadonlyArray<readonly [string, string]> = [
  ['#3a3f55', '#1a1d2c'],
  ['#3d4750', '#1d242a'],
  ['#48414a', '#1f1c22'],
  ['#3b4f4a', '#1a2422'],
  ['#4a3e3e', '#221919'],
  ['#3e4459', '#1a1f30'],
  ['#403b53', '#1d1a26'],
  ['#454a40', '#1d201b'],
]

function pickGradient(seed: string): readonly [string, string] {
  let hash = 0
  for (let i = 0; i < seed.length; i++) {
    hash = (hash << 5) - hash + seed.charCodeAt(i)
    hash |= 0
  }
  const idx = Math.abs(hash) % SEED_GRADIENTS.length
  return SEED_GRADIENTS[idx]
}

export function AvatarBuilder({
  initials,
  defaultUrl,
  hasCustomAvatar,
  onUploaded,
  onResetToDefault,
}: Props) {
  const { t } = useTranslation()
  const [popoverOpen, setPopoverOpen] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [showCustom, setShowCustom] = useState(hasCustomAvatar)
  const [uploading, setUploading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setShowCustom(hasCustomAvatar)
  }, [hasCustomAvatar])

  const gradient = useMemo(
    () => pickGradient(initials || 'X'),
    [initials],
  )

  const handlePickFile = () => {
    inputRef.current?.click()
  }

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      e.target.value = ''
      if (file.size > 2 * 1024 * 1024) {
        setErr(
          t(
            'redesign.onboardingV2.profile.avatarTooBig',
          ),
        )
        return
      }
      setErr(null)
      setUploading(true)
      const localUrl = URL.createObjectURL(file)
      setPreviewUrl(localUrl)
      try {
        const fd = new FormData()
        fd.append('avatar', file)
        const result = await api.uploadAvatar(fd)
        setPreviewUrl(result.avatar_url)
        setShowCustom(true)
        onUploaded?.(result.avatar_url)
        setPopoverOpen(false)
      } catch (uploadErr) {
        const msg =
          uploadErr instanceof Error
            ? uploadErr.message
            : t(
                'redesign.onboardingV2.profile.avatarFail',
              )
        setErr(msg)
      } finally {
        setUploading(false)
      }
    },
    [onUploaded, t],
  )

  const handleResetToDefault = () => {
    setShowCustom(false)
    setPreviewUrl(null)
    onResetToDefault?.()
    setPopoverOpen(false)
  }

  const showInitialsFallback =
    !showCustom && !defaultUrl
  const visibleUrl = showCustom
    ? previewUrl ?? defaultUrl
    : defaultUrl

  return (
    <div className="onb-v2-avatar-wrap">
      <MotionPress
        type="button"
        variant="ghost"
        haptic="light"
        className="onb-v2-avatar"
        onClick={() => setPopoverOpen(true)}
        ariaLabel={t(
          'redesign.profile.avatarEditHint',
        )}
        style={
          showInitialsFallback
            ? {
                background: `linear-gradient(135deg, ${gradient[0]}, ${gradient[1]})`,
              }
            : undefined
        }
      >
        {visibleUrl && !showInitialsFallback ? (
          <img
            src={visibleUrl}
            alt=""
            className="onb-v2-avatar__img"
            draggable={false}
          />
        ) : (
          <span className="onb-v2-avatar__initials">
            {initials || '·'}
          </span>
        )}
        <span
          className="onb-v2-avatar__edit-btn"
          aria-hidden="true"
        >
          <Icon name="edit" size={14} />
        </span>
      </MotionPress>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={handleFileChange}
      />

      {popoverOpen && (
        <div
          className="onb-v2-avatar-popover"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setPopoverOpen(false)
            }
          }}
        >
          <div className="onb-v2-avatar-popover__sheet">
            <h3 className="onb-v2-avatar-popover__title">
              {t(
                'redesign.onboardingV2.profile.avatarSheetTitle',
              )}
            </h3>
            <div className="onb-v2-avatar-popover__row">
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="onb-v2-avatar-popover__btn"
                onClick={handlePickFile}
                disabled={uploading}
              >
                <Icon name="image" size={16} />
                {uploading
                  ? t(
                      'redesign.onboardingV2.profile.avatarUploading',
                    )
                  : t(
                      'redesign.onboardingV2.profile.avatarPick',
                    )}
              </MotionPress>
              {showCustom && (
                <MotionPress
                  type="button"
                  variant="ghost"
                  haptic="light"
                  className="onb-v2-avatar-popover__btn"
                  onClick={handleResetToDefault}
                  disabled={uploading}
                >
                  <Icon name="undo" size={16} />
                  {t(
                    'redesign.onboardingV2.profile.avatarReset',
                  )}
                </MotionPress>
              )}
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="onb-v2-avatar-popover__btn"
                onClick={() => setPopoverOpen(false)}
                disabled={uploading}
              >
                {t(
                  'redesign.onboardingV2.profile.avatarCancel',
                )}
              </MotionPress>
            </div>
            {err && (
              <p
                className="onb-v2-name-error"
                style={{ marginTop: 4 }}
              >
                {err}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
