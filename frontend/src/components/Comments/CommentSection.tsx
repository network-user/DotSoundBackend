import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { CommentCard } from '@/components/Comments/CommentCard'
import { CommentInput } from '@/components/Comments/CommentInput'
import type { TrackComment } from '@/types/api'

interface Props {
  trackId: number
  trackOwnerId: number | null
}

export function CommentSection({ trackId, trackOwnerId }: Props) {
  const [comments, setComments] = useState<TrackComment[]>([])
  const [loading, setLoading] = useState(true)
  const myId = getInternalUserId()
  const isOwner = myId !== null && myId === trackOwnerId

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getComments(trackId)
      setComments(data)
    } finally {
      setLoading(false)
    }
  }, [trackId])

  useEffect(() => { load() }, [load])

  const handleAdd = async (text: string) => {
    try {
      const c = await api.addComment(trackId, text)
      setComments((prev) => [c, ...prev])
    } catch (e) {
      console.error('addComment failed', e)
    }
  }

  const handleDelete = async (id: number) => {
    await api.deleteComment(id)
    setComments((prev) => prev.filter((c) => c.id !== id))
  }

  const handlePin = async (id: number, pinned: boolean) => {
    if (pinned) await api.unpinComment(id)
    else await api.pinComment(id)
    load()
  }

  const handleHide = async (id: number) => {
    await api.hideComment(id)
    setComments((prev) => prev.filter((c) => c.id !== id))
  }

  const handleHideForMe = async (id: number) => {
    await api.hideCommentForMe(id)
    setComments((prev) => prev.filter((c) => c.id !== id))
  }

  const handleVote = async (id: number, isLike: boolean) => {
    await api.voteComment(id, isLike)
    load()
  }

  return (
    <div className="comment-section slide-up">
      <h3 className="comment-section-title">Комментарии</h3>
      <CommentInput onSubmit={handleAdd} />
      {loading ? (
        <div className="comment-skeleton">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="skeleton-comment shimmer" />
          ))}
        </div>
      ) : comments.length === 0 ? (
        <div className="empty-state">Нет комментариев</div>
      ) : (
        <div className="comment-list">
          {comments.map((c) => (
            <CommentCard
              key={c.id}
              comment={c}
              isOwner={isOwner}
              isMine={c.user_id === myId}
              onDelete={handleDelete}
              onPin={handlePin}
              onHide={handleHide}
              onHideForMe={handleHideForMe}
              onVote={handleVote}
            />
          ))}
        </div>
      )}
    </div>
  )
}
