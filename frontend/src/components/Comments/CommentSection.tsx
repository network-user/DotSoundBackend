import {
  useCallback,
  useEffect,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { onWS } from '@/lib/ws'
import { CommentCard } from '@/components/Comments/CommentCard'
import { CommentInput } from '@/components/Comments/CommentInput'
import type { TrackComment } from '@/types/api'

interface Props {
  trackId: number
  trackOwnerId: number | null
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

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getComments(trackId)
      setComments(data)
    } finally {
      setLoading(false)
    }
  }, [trackId])

  useEffect(() => {
    load()
  }, [load])

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
          <button
            type="button"
            className="comment-reply-cancel"
            onClick={() => setReplyTo(null)}
          >
            {t('trackSheet.replyCancel')}
          </button>
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
              <CommentCard
                comment={root}
                isOwner={isOwner}
                isMine={root.user_id === myId}
                isReply={false}
                onReply={() => setReplyTo(root)}
                onDelete={handleDelete}
                onPin={handlePin}
                onHide={handleHide}
                onHideForMe={handleHideForMe}
                onVote={handleVote}
              />
              {(root.replies ?? []).map((r) => (
                <CommentCard
                  key={r.id}
                  comment={r}
                  isOwner={isOwner}
                  isMine={r.user_id === myId}
                  isReply
                  onDelete={handleDelete}
                  onPin={handlePin}
                  onHide={handleHide}
                  onHideForMe={handleHideForMe}
                  onVote={handleVote}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
