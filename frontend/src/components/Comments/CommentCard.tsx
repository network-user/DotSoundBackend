import { useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import type { TrackComment } from '@/types/api'

interface Props {
  comment: TrackComment
  isOwner: boolean
  isMine: boolean
  onDelete: (id: number) => void
  onPin: (id: number, pinned: boolean) => void
  onHide: (id: number) => void
  onHideForMe: (id: number) => void
  onVote: (id: number, isLike: boolean) => void
}

export function CommentCard({
  comment, isOwner, isMine, onDelete, onPin, onHide, onHideForMe, onVote,
}: Props) {
  const [showMenu, setShowMenu] = useState(false)

  return (
    <div className={`comment-card fade-in ${comment.is_pinned ? 'pinned' : ''}`}>
      {comment.is_pinned && (
        <div className="comment-pinned-badge">
          <Icon name="pin" size={12} /> Закреплено
        </div>
      )}
      <div className="comment-header">
        <span className="comment-author">
          {comment.author_label?.trim() ||
            `User #${comment.user_id}`}
        </span>
        <span className="comment-time">
          {new Date(comment.created_at).toLocaleDateString()}
        </span>
        <button className="comment-menu-btn" onClick={() => setShowMenu(!showMenu)}>
          <Icon name="info" size={14} />
        </button>
      </div>
      <p className="comment-text">{comment.text}</p>
      <div className="comment-actions">
        <button
          className="comment-vote-btn"
          onClick={() => onVote(comment.id, true)}
        >
          <Icon name="thumbs-up" size={14} />
          <span className="vote-count">{comment.likes}</span>
        </button>
        <button
          className="comment-vote-btn"
          onClick={() => onVote(comment.id, false)}
        >
          <Icon name="thumbs-down" size={14} />
          <span className="vote-count">{comment.dislikes}</span>
        </button>
      </div>

      {showMenu && (
        <div className="comment-context-menu scale-in">
          {(isMine || isOwner) && (
            <button onClick={() => { onDelete(comment.id); setShowMenu(false) }}>
              <Icon name="trash" size={14} /> Удалить
            </button>
          )}
          {isOwner && (
            <>
              <button onClick={() => { onPin(comment.id, comment.is_pinned); setShowMenu(false) }}>
                <Icon name="pin" size={14} /> {comment.is_pinned ? 'Открепить' : 'Закрепить'}
              </button>
              <button onClick={() => { onHide(comment.id); setShowMenu(false) }}>
                <Icon name="eye" size={14} /> Скрыть для всех
              </button>
            </>
          )}
          <button onClick={() => { onHideForMe(comment.id); setShowMenu(false) }}>
            <Icon name="eye" size={14} /> Скрыть для себя
          </button>
        </div>
      )}
    </div>
  )
}
