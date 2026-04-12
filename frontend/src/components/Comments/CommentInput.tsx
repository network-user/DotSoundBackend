import { useState } from 'react'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  onSubmit: (text: string) => void
}

export function CommentInput({ onSubmit }: Props) {
  const [text, setText] = useState('')

  const handleSubmit = () => {
    if (!text.trim()) return
    onSubmit(text.trim())
    setText('')
  }

  return (
    <div className="comment-input-bar">
      <input
        className="comment-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
        placeholder="Написать комментарий..."
      />
      <button
        className="comment-send-btn"
        onClick={handleSubmit}
        disabled={!text.trim()}
      >
        <Icon name="send" size={18} />
      </button>
    </div>
  )
}
