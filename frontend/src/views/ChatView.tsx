import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { api } from '@/lib/api'
import { onWS, isWSConnected, sendWS } from '@/lib/ws'
import { getInternalUserId } from '@/lib/telegram'
import { ChatBubble } from '@/components/Chat/ChatBubble'
import { ChatInput } from '@/components/Chat/ChatInput'
import { PhotoViewer } from '@/components/Chat/PhotoViewer'
import { Icon } from '@/components/Icon/Icon'
import type { ChatMessage } from '@/types/api'

const ACTIVITY_LABELS: Record<string, string> = {
  typing: 'печатает...',
  recording_audio: 'записывает аудио...',
  sending_photo: 'отправляет фото...',
}

export function ChatView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const conversationId = id ? Number(id) : null
  const title = (location.state as { title?: string } | null)?.title ?? null
  const onBack = () => navigate('/chats')
  const active = true
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [initialLastRead, setInitialLastRead] = useState<number | null>(null)
  const [peerStatus, setPeerStatus] =
    useState<string>('offline')
  const [peerActivity, setPeerActivity] =
    useState<string | null>(null)
  const [peerLastSeen, setPeerLastSeen] =
    useState<number>(0)
  const [peerId, setPeerId] = useState<
    number | null
  >(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [isBlocked, setIsBlocked] =
    useState(false)
  const [viewingPhoto, setViewingPhoto] =
    useState<string | null>(null)
  const [devOpen, setDevOpen] = useState(false)
  const [debugLog, setDebugLog] = useState<
    string[]
  >([])
  const addDebug = useCallback(
    (msg: string) =>
      setDebugLog((p) => [
        ...p.slice(-19),
        `${new Date().toLocaleTimeString()} ${msg}`,
      ]),
    [],
  )
  const listRef = useRef<HTMLDivElement>(null)
  const activityTimer =
    useRef<ReturnType<typeof setTimeout>>()
  const uploadAbort =
    useRef<AbortController | null>(null)
  const uploadTempId = useRef<number | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const myId = getInternalUserId()

  const mergeIncomingMessage = (
    data: Record<string, unknown>,
  ) => {
    const msgId = Number(
      data.id ?? data.message_id,
    )
    if (!Number.isFinite(msgId)) return
    const nextMessage = {
      id: msgId,
      conversation_id: Number(
        data.conversation_id,
      ),
      sender_id: Number(data.sender_id),
      type: String(data.type || 'text'),
      content: String(data.content || ''),
      reply_to_id:
        typeof data.reply_to_id === 'number'
          ? data.reply_to_id
          : null,
      shared_track_id:
        typeof data.shared_track_id === 'number'
          ? data.shared_track_id
          : null,
      created_at: String(data.created_at),
      attachments: Array.isArray(data.attachments)
        ? data.attachments
        : [],
      reactions: Array.isArray(data.reactions)
        ? data.reactions
        : [],
    } as ChatMessage

    setMessages((prev) => {
      const index = prev.findIndex(
        (msg) => msg.id === msgId,
      )
      if (index === -1) {
        return [...prev, nextMessage]
      }
      return prev.map((msg) =>
        msg.id === msgId
          ? { ...msg, ...nextMessage }
          : msg,
      )
    })
  }

  const applyReactionEvent = (
    data: Record<string, unknown>,
  ) => {
    const msgId = Number(data.message_id)
    const userId = Number(data.user_id)
    const reactionType = String(
      data.reaction_type || '',
    )
    const action = String(data.action || 'add')
    if (
      !Number.isFinite(msgId) ||
      !Number.isFinite(userId) ||
      !reactionType
    ) {
      return
    }

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== msgId) return msg
        const existing = msg.reactions.some(
          (reaction) =>
            reaction.user_id === userId &&
            reaction.reaction_type === reactionType,
        )
        if (action === 'remove') {
          return {
            ...msg,
            reactions: msg.reactions.filter(
              (reaction) =>
                !(
                  reaction.user_id === userId &&
                  reaction.reaction_type ===
                    reactionType
                ),
            ),
          }
        }
        if (existing) return msg
        return {
          ...msg,
          reactions: [
            ...msg.reactions,
            {
              user_id: userId,
              reaction_type: reactionType,
            },
          ],
        }
      }),
    )
  }

  const loadMessages = useCallback(async () => {
    if (!conversationId) return
    setLoading(true)
    try {
      const [msgs, chatInfo] = await Promise.all([
        api.getMessages(conversationId),
        api.getChat(conversationId).catch(() => null),
      ])
      if (chatInfo?.member?.last_read_message_id != null) {
        setInitialLastRead(chatInfo.member.last_read_message_id)
      }
      setMessages(msgs.reverse())
    } finally {
      setLoading(false)
    }
  }, [conversationId])

  const refreshPresence = useCallback(() => {
    if (!conversationId) return
    api
      .getChatPresence(conversationId)
      .then((res) => {
        const keys = Object.keys(res.members)
        const vals = Object.values(res.members)
        if (vals.length > 0) {
          setPeerId(Number(keys[0]))
          setPeerStatus(vals[0].status)
          setPeerLastSeen(vals[0].last_seen)
        } else {
          setPeerStatus('self')
        }
      })
      .catch(() => {
        setPeerStatus('self')
      })
  }, [conversationId])

  useEffect(() => {
    if (!active || !conversationId) return
    loadMessages()
    refreshPresence()
    api
      .listBlocks()
      .then((res) => {
        if (peerId) {
          setIsBlocked(
            res.blocked_user_ids.includes(
              peerId,
            ),
          )
        }
      })
      .catch(() => {})
  }, [
    active,
    conversationId,
    loadMessages,
    refreshPresence,
    peerId,
  ])

  useEffect(() => {
    if (!conversationId) return
    const interval = setInterval(() => {
      refreshPresence()
    }, 10_000)
    return () => clearInterval(interval)
  }, [conversationId, refreshPresence])

  useEffect(() => {
    if (
      !conversationId ||
      peerStatus === 'self'
    )
      return
    const poll = async () => {
      try {
        const res =
          await api.getActivity(conversationId)
        if (res.activities.length > 0) {
          const a = res.activities[0]
          setPeerActivity(a.activity)
          setPeerStatus('online')
          if (activityTimer.current)
            clearTimeout(activityTimer.current)
          activityTimer.current = setTimeout(
            () => setPeerActivity(null),
            4000,
          )
        }
      } catch {}
    }
    const interval = setInterval(poll, 1000)
    return () => clearInterval(interval)
  }, [conversationId, peerStatus])

  useEffect(() => {
    if (!conversationId) return
    const interval = setInterval(async () => {
      try {
        const msgs =
          await api.getMessages(conversationId)
        const sorted = msgs.reverse()
        setMessages((prev) => {
          if (sorted.length === 0) return prev
          const lastPrev = prev[prev.length - 1]
          const lastNew =
            sorted[sorted.length - 1]
          if (
            lastPrev &&
            lastNew &&
            lastPrev.id === lastNew.id
          ) {
            return prev
          }
          return sorted
        })
      } catch {}
    }, 3_000)
    return () => clearInterval(interval)
  }, [conversationId])

  useEffect(() => {
    if (!conversationId) return

    addDebug(
      `WS handlers for conv ${conversationId}, ws=${isWSConnected() ? 'OPEN' : 'CLOSED'}`,
    )

    const offAll = onWS('*', (data) => {
      addDebug(
        `WS event: ${String(data.event)} conv=${data.conversation_id}`,
      )
    })

    const offNew = onWS(
      'message.new',
      (data) => {
        if (
          data.conversation_id ===
          conversationId
        ) {
          mergeIncomingMessage(data)
          const msgId = Number(
            data.id ?? data.message_id,
          )
          if (
            Number.isFinite(msgId) &&
            data.sender_id !== myId
          ) {
            api.markRead(conversationId, msgId)
          }
          setPeerActivity(null)
        }
      },
    )

    const offDel = onWS(
      'message.deleted',
      (data) => {
        if (
          data.conversation_id ===
          conversationId
        ) {
          setMessages((prev) =>
            prev.filter(
              (m) => m.id !== data.message_id,
            ),
          )
        }
      },
    )

    const offActivity = onWS(
      'activity',
      (data) => {
        addDebug(
          `activity: ${data.activity} from=${data.user_id} conv=${data.conversation_id} match=${data.conversation_id === conversationId} notMe=${data.user_id !== myId}`,
        )
        if (
          data.conversation_id ===
            conversationId &&
          data.user_id !== myId
        ) {
          const activity =
            data.activity as string
          if (activity === 'idle') {
            setPeerActivity(null)
          } else {
            setPeerActivity(activity)
            if (activityTimer.current)
              clearTimeout(activityTimer.current)
            activityTimer.current = setTimeout(
              () => setPeerActivity(null),
              5000,
            )
          }
        }
      },
    )

    const offReaction = onWS(
      'message.reaction',
      (data) => {
        if (
          data.conversation_id === conversationId
        ) {
          applyReactionEvent(data)
        }
      },
    )

    return () => {
      offAll()
      offNew()
      offDel()
      offActivity()
      offReaction()
      if (activityTimer.current)
        clearTimeout(activityTimer.current)
    }
  }, [conversationId, myId])

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  const addMessage = (msg: ChatMessage) => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === msg.id)) return prev
      return [...prev, msg]
    })
  }

  const handleSend = async (content: string) => {
    if (!conversationId || !content.trim()) return
    const msg = await api.sendMessage(conversationId, content)
    addMessage(msg)
  }

  const handleSendPhoto = async (file: File, caption: string) => {
    if (!conversationId) return

    const localUrl = URL.createObjectURL(file)
    const tempId = -Date.now()
    uploadTempId.current = tempId
    const controller = new AbortController()
    uploadAbort.current = controller

    const placeholder: ChatMessage = {
      id: tempId,
      conversation_id: conversationId,
      sender_id: myId ?? 0,
      type: 'photo',
      content: caption,
      reply_to_id: null,
      shared_track_id: null,
      created_at: new Date().toISOString(),
      attachments: [{
        id: 0,
        file_key: localUrl,
        file_type: 'photo',
      }],
      reactions: [],
      _uploading: true,
    } as ChatMessage & { _uploading?: boolean }
    setMessages((prev) => [...prev, placeholder])

    try {
      const fd = new FormData()
      fd.append('file', file)
      const msg = await api.sendPhoto(conversationId, fd, controller.signal)
      if (caption) {
        await api.sendMessage(conversationId, caption)
      }
      setMessages((prev) =>
        prev.map((m) => (m.id === tempId ? { ...msg, _uploading: false } : m))
      )
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId))
    } finally {
      URL.revokeObjectURL(localUrl)
      uploadAbort.current = null
      uploadTempId.current = null
    }
  }

  const handleCancelUpload = () => {
    uploadAbort.current?.abort()
    if (uploadTempId.current !== null) {
      setMessages((prev) =>
        prev.filter((m) => m.id !== uploadTempId.current)
      )
    }
    uploadAbort.current = null
    uploadTempId.current = null
  }

  const handleSendVoice = async (blob: Blob) => {
    if (!conversationId) return
    const ext = blob.type.includes('webm')
      ? 'webm'
      : blob.type.includes('mp4')
        ? 'mp4'
        : 'ogg'
    const fd = new FormData()
    fd.append('file', blob, `voice.${ext}`)
    const msg = await api.sendVoice(conversationId, fd)
    addMessage(msg)
  }

  const handleDelete = async (msgId: number) => {
    await api.deleteMessage(msgId)
    setMessages((prev) => prev.filter((m) => m.id !== msgId))
  }

  const handleReaction = async (msgId: number, type: string) => {
    const hasOwnReaction = messages
      .find((msg) => msg.id === msgId)
      ?.reactions.some(
        (reaction) =>
          reaction.user_id === myId &&
          reaction.reaction_type === type,
      )
    if (hasOwnReaction) {
      await api.removeReaction(msgId, type)
      return
    }
    await api.addReaction(msgId, type)
  }

  useEffect(() => {
    if (!menuOpen) return
    const handleClick = (e: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(
          e.target as Node,
        )
      ) {
        setMenuOpen(false)
      }
    }
    document.addEventListener(
      'mousedown',
      handleClick,
    )
    return () =>
      document.removeEventListener(
        'mousedown',
        handleClick,
      )
  }, [menuOpen])

  const handleBlock = async () => {
    if (!peerId) return
    if (isBlocked) {
      await api.unblockUser(peerId)
      setIsBlocked(false)
    } else {
      await api.blockUser(peerId)
      setIsBlocked(true)
    }
    setMenuOpen(false)
  }

  const formatLastSeen = (ts: number) => {
    if (!ts) return 'давно'
    const d = new Date(ts * 1000)
    const now = Date.now()
    const diff = (now - d.getTime()) / 1000
    if (diff < 60) return 'только что'
    if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`
    return d.toLocaleDateString()
  }

  const renderStatusLine = () => {
    if (peerStatus === 'self') return null
    if (peerActivity && ACTIVITY_LABELS[peerActivity]) {
      return (
        <span className="chat-status-text activity">
          {ACTIVITY_LABELS[peerActivity]}
        </span>
      )
    }
    if (peerStatus === 'online') {
      return <span className="chat-status-text online">в сети</span>
    }
    if (!peerLastSeen) {
      return (
        <span className="chat-status-text offline">
          не в сети
        </span>
      )
    }
    return (
      <span className="chat-status-text offline">
        был(а) {formatLastSeen(peerLastSeen)}
      </span>
    )
  }

  if (!active) return null

  return (
    <div className="chat-view slide-in">
      <div className="chat-view-header">
        <button
          className="chat-back-btn"
          onClick={onBack}
        >
          <Icon
            name="chevron"
            size={20}
            className="chat-back-icon"
          />
        </button>
        {peerStatus === 'self' && (
          <div className="chat-header-avatar saved">
            <Icon name="heart" size={20} />
          </div>
        )}
        <div className="chat-header-info">
          <div className="chat-header-top">
            <span className="chat-view-title">
              {title || 'Чат'}
            </span>
            {peerActivity ? (
              <span className="presence-dot activity-pulse" />
            ) : (
              peerStatus === 'online' && (
                <span className="presence-dot online" />
              )
            )}
          </div>
          <div className="chat-header-status">
            {peerStatus === 'self' ? (
              <span className="chat-status-text offline">
                личное пространство
              </span>
            ) : (
              renderStatusLine()
            )}
          </div>
        </div>
        {peerStatus !== 'self' && (
          <div
            className="chat-menu-wrap"
            ref={menuRef}
          >
            <button
              className="chat-menu-btn icon-btn"
              onClick={() =>
                setMenuOpen((v) => !v)
              }
            >
              <Icon
                name="more-vertical"
                size={20}
              />
            </button>
            {menuOpen && (
              <div className="chat-dropdown scale-in">
                <button
                  className="chat-dropdown-item"
                  onClick={handleBlock}
                >
                  <Icon
                    name={
                      isBlocked
                        ? 'check'
                        : 'block'
                    }
                    size={16}
                  />
                  {isBlocked
                    ? 'Разблокировать'
                    : 'Заблокировать'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="chat-messages" ref={listRef}>
        {loading ? (
          <div className="chat-skeleton">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className={`skeleton-bubble ${i % 2 === 0 ? 'left' : 'right'} shimmer`} />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <div className="chat-empty-state">
            {peerStatus === 'self' ? (
              <>
                <div className="chat-empty-icon">
                  <Icon name="heart" size={32} />
                </div>
                <div className="chat-empty-title">Избранное</div>
                <div className="chat-empty-desc">
                  Сохраняйте сюда важные сообщения, ссылки на треки и заметки
                </div>
              </>
            ) : (
              <div className="chat-empty-desc">Напишите первое сообщение</div>
            )}
          </div>
        ) : (
          (() => {
            const items: React.ReactNode[] = []
            let currentUnreadRendered = false
            let prevDateStr = ''

            messages.forEach((msg) => {
              const dateObj = new Date(msg.created_at)
              const dateStr = dateObj.toLocaleDateString(undefined, {
                day: 'numeric',
                month: 'short',
                year:
                  dateObj.getFullYear() === new Date().getFullYear()
                    ? undefined
                    : 'numeric',
              })

              if (dateStr !== prevDateStr) {
                items.push(
                  <div key={`date-${msg.id}`} className="chat-date-separator">
                    <span>{dateStr}</span>
                  </div>
                )
                prevDateStr = dateStr
              }

              if (
                !currentUnreadRendered &&
                initialLastRead !== null &&
                msg.id > initialLastRead &&
                msg.sender_id !== myId
              ) {
                items.push(
                  <div key={`unread-${msg.id}`} className="chat-unread-separator">
                    <span>Новые сообщения</span>
                  </div>
                )
                currentUnreadRendered = true
              }

              items.push(
                <ChatBubble
                  key={msg.id}
                  message={msg}
                  isMine={msg.sender_id === myId}
                  onDelete={handleDelete}
                  onReaction={handleReaction}
                  onCancelUpload={
                    (msg as any)._uploading ? handleCancelUpload : undefined
                  }
                  onViewPhoto={setViewingPhoto}
                />
              )
            })

            return items
          })()
        )}
        {peerActivity && (
          <div className="typing-indicator">
            <span /><span /><span />
            {peerActivity !== 'typing' &&
              ACTIVITY_LABELS[peerActivity] && (
                <span className="activity-label">
                  {ACTIVITY_LABELS[peerActivity]}
                </span>
              )}
          </div>
        )}
      </div>
      <ChatInput
        conversationId={conversationId}
        onSend={handleSend}
        onSendPhoto={handleSendPhoto}
        onSendVoice={handleSendVoice}
      />
      {viewingPhoto && (
        <PhotoViewer
          src={viewingPhoto}
          onClose={() => setViewingPhoto(null)}
        />
      )}
      {!devOpen && (
        <button
          style={{
            position: 'fixed',
            bottom: 80,
            right: 10,
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'rgba(40,40,40,0.85)',
            border:
              '1px solid rgba(255,255,255,0.12)',
            color: 'rgba(255,255,255,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            zIndex: 9999,
            backdropFilter: 'blur(6px)',
          }}
          onClick={() => setDevOpen(true)}
        >
          <Icon name="settings" size={14} />
        </button>
      )}
      {devOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: 80,
            left: 8,
            right: 8,
            background: 'rgba(10,10,10,0.95)',
            border:
              '1px solid rgba(255,255,255,0.12)',
            borderRadius: 10,
            padding: '8px 10px',
            fontSize: 10,
            fontFamily: 'monospace',
            color: 'rgba(255,255,255,0.7)',
            zIndex: 9999,
            maxHeight: '40vh',
            overflow: 'auto',
            backdropFilter: 'blur(8px)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 6,
              flexWrap: 'wrap',
            }}
          >
            <span
              style={{
                fontWeight: 700,
                color: '#fff',
                fontSize: 11,
              }}
            >
              DevTools
            </span>
            <span
              style={{
                padding: '1px 5px',
                borderRadius: 4,
                fontSize: 9,
                background: isWSConnected()
                  ? 'rgba(74,222,128,0.2)'
                  : 'rgba(239,68,68,0.2)',
                color: isWSConnected()
                  ? '#4ade80'
                  : '#ef4444',
              }}
            >
              WS{' '}
              {isWSConnected()
                ? 'OPEN'
                : 'CLOSED'}
            </span>
            <span>
              peer:{String(peerId)}
            </span>
            <span>me:{String(myId)}</span>
            <div
              style={{
                marginLeft: 'auto',
                display: 'flex',
                gap: 4,
              }}
            >
              <button
                style={{
                  fontSize: 9,
                  padding: '3px 8px',
                  background:
                    'rgba(255,255,255,0.08)',
                  color: '#fff',
                  border:
                    '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
                onClick={() => {
                  if (!conversationId) return
                  addDebug(
                    `SEND typing ws=${isWSConnected()}`,
                  )
                  sendWS({
                    event: 'activity',
                    conversation_id:
                      conversationId,
                    activity: 'typing',
                  })
                  api
                    .postActivity(
                      conversationId,
                      'typing',
                    )
                    .then(() =>
                      addDebug(
                        'REST typing OK',
                      ),
                    )
                    .catch((e: Error) =>
                      addDebug(
                        `REST err: ${e.message}`,
                      ),
                    )
                }}
              >
                Test typing
              </button>
              <button
                style={{
                  fontSize: 9,
                  padding: '3px 8px',
                  background:
                    'rgba(255,255,255,0.08)',
                  color: '#fff',
                  border:
                    '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
                onClick={() =>
                  setDebugLog([])
                }
              >
                Clear
              </button>
              <button
                style={{
                  fontSize: 9,
                  padding: '3px 8px',
                  background:
                    'rgba(255,255,255,0.08)',
                  color: '#fff',
                  border:
                    '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
                onClick={() =>
                  setDevOpen(false)
                }
              >
                Close
              </button>
            </div>
          </div>
          <div
            style={{
              borderTop:
                '1px solid rgba(255,255,255,0.08)',
              paddingTop: 4,
            }}
          >
            {debugLog.length === 0 ? (
              <div
                style={{
                  opacity: 0.3,
                  padding: 4,
                }}
              >
                No events yet
              </div>
            ) : (
              debugLog.map((line, i) => (
                <div
                  key={i}
                  style={{
                    padding: '1px 0',
                    borderBottom:
                      '1px solid rgba(255,255,255,0.03)',
                  }}
                >
                  {line}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
