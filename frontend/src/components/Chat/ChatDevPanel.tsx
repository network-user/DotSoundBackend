import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import { isWSConnected, sendWS } from '@/lib/ws'

interface Props {
  open: boolean
  onOpen: () => void
  onClose: () => void
  conversationId: number | null
  peerId: number | null
  myId: number | null
  debugLog: string[]
  onClearLog: () => void
  onAddDebug: (msg: string) => void
}

export function ChatDevPanel({
  open,
  onOpen,
  onClose,
  conversationId,
  peerId,
  myId,
  debugLog,
  onClearLog,
  onAddDebug,
}: Props) {
  if (!import.meta.env.DEV) return null

  if (!open) {
    return (
      <MotionPress
        type="button"
        variant="icon"
        className="re-chat-dev-toggle"
        ariaLabel="Open dev tools"
        onClick={onOpen}
      >
        <Icon name="settings" size={14} />
      </MotionPress>
    )
  }

  const wsOk = isWSConnected()

  const handleTestTyping = () => {
    if (!conversationId) return
    onAddDebug(`SEND typing ws=${wsOk}`)
    sendWS({
      event: 'activity',
      conversation_id: conversationId,
      activity: 'typing',
    })
    api
      .postActivity(conversationId, 'typing')
      .then(() => onAddDebug('REST typing OK'))
      .catch((e: Error) =>
        onAddDebug(`REST err: ${e.message}`),
      )
  }

  return (
    <div className="re-chat-dev-panel">
      <div className="re-chat-dev-panel__head">
        <span className="re-chat-dev-panel__title">DevTools</span>
        <span
          className={`re-chat-dev-panel__ws${wsOk ? ' is-on' : ' is-off'}`}
        >
          WS {wsOk ? 'OPEN' : 'CLOSED'}
        </span>
        <span className="re-chat-dev-panel__id">
          peer:{String(peerId)}
        </span>
        <span className="re-chat-dev-panel__id">
          me:{String(myId)}
        </span>
        <div className="re-chat-dev-panel__actions">
          <button
            type="button"
            className="re-chat-dev-panel__btn"
            onClick={handleTestTyping}
          >
            Test typing
          </button>
          <button
            type="button"
            className="re-chat-dev-panel__btn"
            onClick={onClearLog}
          >
            Clear
          </button>
          <button
            type="button"
            className="re-chat-dev-panel__btn"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
      <div className="re-chat-dev-panel__log">
        {debugLog.length === 0 ? (
          <div className="re-chat-dev-panel__empty">
            No events yet
          </div>
        ) : (
          debugLog.map((line, i) => (
            <div key={i} className="re-chat-dev-panel__line">
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
