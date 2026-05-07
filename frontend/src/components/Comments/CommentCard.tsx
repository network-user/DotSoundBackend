import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
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
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="comment-reply-link"
              onClick={onReply}
            >
              {t('trackSheet.replyAction')}
            </MotionPress>
          )}
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="comment-menu-btn"
            onClick={() => setShowMenu(!showMenu)}
          >
            <Icon name="info" size={14} />
          </MotionPress>
        </div>
      </div>
      <p className="comment-text" dir="auto">{comment.text}</p>
      <div className="comment-actions">
        <MotionPress
          type="button"
          variant="ghost"
          haptic="selection"
          className="comment-vote-btn"
          onClick={() => onVote(comment.id, true)}
        >
          <Icon name="thumbs-up" size={14} />
          <span className="vote-count">{comment.likes}</span>
        </MotionPress>
        <MotionPress
          type="button"
          variant="ghost"
          haptic="selection"
          className="comment-vote-btn"
          onClick={() => onVote(comment.id, false)}
        >
          <Icon name="thumbs-down" size={14} />
          <span className="vote-count">{comment.dislikes}</span>
        </MotionPress>
      </div>

      {showMenu && (
        <div className="comment-context-menu scale-in">
          {(isMine || isOwner) && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="medium"
              onClick={() => {
                onDelete(comment.id)
                setShowMenu(false)
              }}
            >
              <Icon name="trash" size={14} />{' '}
              {t('trackSheet.commentDelete')}
            </MotionPress>
          )}
          {isOwner && isRootComment && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              onClick={() => {
                onPin(comment.id, comment.is_pinned)
                setShowMenu(false)
              }}
            >
              <Icon name="pin" size={14} />{' '}
              {comment.is_pinned
                ? t('trackSheet.commentUnpin')
                : t('trackSheet.commentPin')}
            </MotionPress>
          )}
          {isOwner && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              onClick={() => {
                onHide(comment.id)
                setShowMenu(false)
              }}
            >
              <Icon name="eye" size={14} />{' '}
              {t('trackSheet.commentHideAll')}
            </MotionPress>
          )}
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            onClick={() => {
              onHideForMe(comment.id)
              setShowMenu(false)
            }}
          >
            <Icon name="eye" size={14} />{' '}
            {t('trackSheet.commentHideSelf')}
          </MotionPress>
        </div>
      )}
    </div>
  )
}
