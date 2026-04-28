import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import type { TrackComment } from '@/types/api'

interface Props {
  comment: TrackComment
  isOwner: boolean
  isMine: boolean
  onReply?: () => void
  onDelete: (id: number) => void
  onPin: (id: number, pinned: boolean) => void
  onHide: (id: number) => void
  onHideForMe: (id: number) => void
  onVote: (id: number, isLike: boolean) => void
}

export function CommentCard({
  comment,
  isOwner,
  isMine,
  onReply,
  onDelete,
  onPin,
  onHide,
  onHideForMe,
  onVote,
}: Props) {
  const { t } = useTranslation()
  const [showMenu, setShowMenu] = useState(false)
  const isRootComment = comment.parent_id == null

  return (
    <div
      className={`comment-card fade-in${comment.is_pinned ? ' pinned' : ''}`}
    >
      {comment.is_pinned && isRootComment && (
        <div className="comment-pinned-badge">
          <Icon name="pin" size={12} />{' '}
          {t('trackSheet.commentPinned')}
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
        <div className="comment-header-actions">
          {onReply && (
            <button
              type="button"
              className="comment-reply-link"
              onClick={onReply}
            >
              {t('trackSheet.replyAction')}
            </button>
          )}
          <button
            className="comment-menu-btn"
            onClick={() => setShowMenu(!showMenu)}
            type="button"
          >
            <Icon name="info" size={14} />
          </button>
        </div>
      </div>
      <p className="comment-text">{comment.text}</p>
      <div className="comment-actions">
        <button
          className="comment-vote-btn"
          type="button"
          onClick={() => onVote(comment.id, true)}
        >
          <Icon name="thumbs-up" size={14} />
          <span className="vote-count">{comment.likes}</span>
        </button>
        <button
          className="comment-vote-btn"
          type="button"
          onClick={() => onVote(comment.id, false)}
        >
          <Icon name="thumbs-down" size={14} />
          <span className="vote-count">{comment.dislikes}</span>
        </button>
      </div>

      {showMenu && (
        <div className="comment-context-menu scale-in">
          {(isMine || isOwner) && (
            <button
              type="button"
              onClick={() => {
                onDelete(comment.id)
                setShowMenu(false)
              }}
            >
              <Icon name="trash" size={14} />{' '}
              {t('trackSheet.commentDelete')}
            </button>
          )}
          {isOwner && isRootComment && (
            <button
              type="button"
              onClick={() => {
                onPin(comment.id, comment.is_pinned)
                setShowMenu(false)
              }}
            >
              <Icon name="pin" size={14} />{' '}
              {comment.is_pinned
                ? t('trackSheet.commentUnpin')
                : t('trackSheet.commentPin')}
            </button>
          )}
          {isOwner && (
            <button
              type="button"
              onClick={() => {
                onHide(comment.id)
                setShowMenu(false)
              }}
            >
              <Icon name="eye" size={14} />{' '}
              {t('trackSheet.commentHideAll')}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              onHideForMe(comment.id)
              setShowMenu(false)
            }}
          >
            <Icon name="eye" size={14} />{' '}
            {t('trackSheet.commentHideSelf')}
          </button>
        </div>
      )}
    </div>
  )
}
