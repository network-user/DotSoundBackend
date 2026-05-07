import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { onWS } from '@/lib/ws'
import { CommentCard } from '@/components/Comments/CommentCard'
import { CommentInput } from '@/components/Comments/CommentInput'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import type { TrackComment } from '@/types/api'

interface Props {
  trackId: number
  trackOwnerId: number | null
}

interface BranchProps {
  comment: TrackComment
  depth: number
  isOwner: boolean
  myId: number | null
  onPickReply: (c: TrackComment) => void
  onDelete: (id: number) => void
  onPin: (id: number, pinned: boolean) => void
  onHide: (id: number) => void
  onHideForMe: (id: number) => void
  onVote: (id: number, isLike: boolean) => void
}

function CommentBranch({
  comment,
  depth,
  isOwner,
  myId,
  onPickReply,
  onDelete,
  onPin,
  onHide,
  onHideForMe,
  onVote,
}: BranchProps) {
  const nest =
    depth > 0
      ? {
          marginLeft: Math.min(depth, 15) * 12,
          paddingLeft: 10,
          borderLeft:
            '2px solid rgba(255, 255, 255, 0.08)',
        }
      : undefined

  return (
    <div
      className="comment-branch-node"
      style={nest}
      data-comment-id={comment.id}
    >
      <CommentCard
        comment={comment}
        isOwner={isOwner}
        isMine={comment.user_id === myId}
        onReply={() => onPickReply(comment)}
        onDelete={onDelete}
        onPin={onPin}
        onHide={onHide}
        onHideForMe={onHideForMe}
        onVote={onVote}
      />
      {(comment.replies ?? []).map((ch) => (
        <CommentBranch
          key={ch.id}
          comment={ch}
          depth={depth + 1}
          isOwner={isOwner}
          myId={myId}
          onPickReply={onPickReply}
          onDelete={onDelete}
          onPin={onPin}
          onHide={onHide}
          onHideForMe={onHideForMe}
          onVote={onVote}
        />
      ))}
    </div>
  )
}

export function CommentSection({
  trackId,
  trackOwnerId,
}: Props) {
  const { t } = useTranslation()
  const [comments, setComments] = useState<
    TrackComment[]
  >([])
  const [loading, setLoading] = useState(true)
  const [replyTo, setReplyTo] =
    useState<TrackComment | null>(null)
  const myId = getInternalUserId()
  const isOwner =
    myId !== null && myId === trackOwnerId
  const { pendingCommentFocus } = usePlayerMeta()
  const { clearPendingCommentFocus } =
    usePlayerActions()
  const pendingRef = useRef(pendingCommentFocus)
  pendingRef.current = pendingCommentFocus

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const p = pendingRef.current
      const fc =
        p && p.trackId === trackId
          ? p.commentId
          : undefined
      const data = await api.getComments(
        trackId,
        undefined,
        20,
        fc,
      )
      setComments(data)
    } finally {
      setLoading(false)
    }
  }, [trackId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (loading) return
    if (pendingCommentFocus?.trackId !== trackId) {
      return
    }
    const cid = pendingCommentFocus.commentId
    const el = document.querySelector(
      `[data-comment-id="${cid}"]`,
    ) as HTMLElement | null
    if (el) {
      el.scrollIntoView({
        block: 'center',
        behavior: 'smooth',
      })
      el.classList.add('comment-highlight-flash')
      window.setTimeout(() => {
        el.classList.remove('comment-highlight-flash')
      }, 1800)
      clearPendingCommentFocus()
      return
    }
    const timer = window.setTimeout(() => {
      clearPendingCommentFocus()
    }, 500)
    return () => window.clearTimeout(timer)
  }, [
    loading,
    comments,
    trackId,
    pendingCommentFocus,
    clearPendingCommentFocus,
  ])

  useEffect(() => {
    const offNew = onWS('comment.new', (data) => {
      if (data.track_id !== trackId) return
      if (data.user_id === myId) return
      load()
    })
    const offDel = onWS('comment.deleted', (data) => {
      if (data.track_id !== trackId) return
      load()
    })
    return () => {
      offNew()
      offDel()
    }
  }, [trackId, myId, load])

  const handleAdd = async (text: string) => {
    try {
      await api.addComment(
        trackId,
        text,
        replyTo?.id,
      )
      setReplyTo(null)
      await load()
    } catch (e) {
      console.error('addComment failed', e)
    }
  }

  const handleDelete = async (id: number) => {
    await api.deleteComment(id)
    await load()
  }

  const handlePin = async (id: number, pinned: boolean) => {
    if (pinned) await api.unpinComment(id)
    else await api.pinComment(id)
    await load()
  }

  const handleHide = async (id: number) => {
    await api.hideComment(id)
    await load()
  }

  const handleHideForMe = async (id: number) => {
    await api.hideCommentForMe(id)
    await load()
  }

  const handleVote = async (
    id: number,
    isLike: boolean,
  ) => {
    await api.voteComment(id, isLike)
    await load()
  }

  return (
    <div className="comment-section slide-up">
      <h3 className="comment-section-title">
        {t('trackSheet.commentsTitle')}
      </h3>
      {replyTo && (
        <div className="comment-reply-context">
          <span className="comment-reply-label">
            {t('trackSheet.replyingTo', {
              name:
                replyTo.author_label?.trim() ||
                `User #${replyTo.user_id}`,
            })}
          </span>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="comment-reply-cancel"
            onClick={() => setReplyTo(null)}
          >
            {t('trackSheet.replyCancel')}
          </MotionPress>
        </div>
      )}
      <CommentInput onSubmit={handleAdd} />
      {loading ? (
        <div className="comment-skeleton">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="skeleton-comment shimmer"
            />
          ))}
        </div>
      ) : comments.length === 0 ? (
        <div className="empty-state">
          {t('trackSheet.commentsEmpty')}
        </div>
      ) : (
        <div className="comment-list">
          {comments.map((root) => (
            <div
              key={root.id}
              className="comment-thread"
            >
              <CommentBranch
                comment={root}
                depth={0}
                isOwner={isOwner}
                myId={myId}
                onPickReply={setReplyTo}
                onDelete={handleDelete}
                onPin={handlePin}
                onHide={handleHide}
                onHideForMe={handleHideForMe}
                onVote={handleVote}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
