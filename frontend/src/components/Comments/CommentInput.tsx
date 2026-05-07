import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'

const MAX_COMMENT = 1000
const COUNTER_SHOW = 800

interface Props {
  onSubmit: (text: string) => void
}

export function CommentInput({ onSubmit }: Props) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const isOver = text.length > MAX_COMMENT
  const showCount = text.length >= COUNTER_SHOW

  const handleSubmit = () => {
    if (!text.trim() || isOver) return
    onSubmit(text.trim())
    setText('')
  }

  return (
    <div className="comment-input-bar">
      <div className="comment-input-wrap">
        <input
          className="comment-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSubmit()
          }}
          placeholder={t(
            'trackSheet.commentPlaceholder',
            'Написать комментарий...',
          )}
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
        ariaLabel={t(
          'trackSheet.commentSend',
          'Отправить',
        )}
        onClick={handleSubmit}
        disabled={!text.trim() || isOver}
      >
        <Icon name="send" size={18} />
      </MotionPress>
    </div>
  )
}
