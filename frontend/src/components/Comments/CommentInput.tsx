import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

const MAX_COMMENT = 1000
const COUNTER_SHOW = 800

interface Props {
  // Returns true when the comment was accepted (draft may be cleared),
  // false when it failed (draft is kept so the user can retry).
  onSubmit: (text: string) => Promise<boolean>
}

export function CommentInput({ onSubmit }: Props) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const isOver = text.length > MAX_COMMENT
  const showCount = text.length >= COUNTER_SHOW
  const canSubmit = Boolean(text.trim()) && !isOver && !submitting

  const handleSubmit = async () => {
    const value = text.trim()
    if (!value || isOver || submitting) return
    setSubmitting(true)
    try {
      const ok = await onSubmit(value)
      // Only clear on success; on failure the draft stays put.
      if (ok) setText('')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="comment-input-bar">
      <div className="comment-input-wrap">
        <input
          className="comment-input"
          value={text}
          disabled={submitting}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void handleSubmit()
          }}
          placeholder={t('trackSheet.commentPlaceholder', {
            defaultValue: 'Написать комментарий...',
          })}
          maxLength={MAX_COMMENT + 50}
        />
        {showCount && (
          <span
            className={`char-counter comment-counter ${isOver ? 'over' : ''}`}
          >
            {text.length}/{MAX_COMMENT}
          </span>
        )}
      </div>
      <MotionPress
        type="button"
        variant="primary"
        haptic="medium"
        className="comment-send-btn"
        ariaLabel={t('trackSheet.commentSend', {
          defaultValue: 'Отправить',
        })}
        aria-busy={submitting}
        onClick={() => void handleSubmit()}
        disabled={!canSubmit}
      >
        <Icon name="send" size={18} />
      </MotionPress>
    </div>
  )
}
