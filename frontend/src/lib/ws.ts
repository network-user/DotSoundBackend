type EventHandler = (data: Record<string, unknown>) => void

let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectDelay = 1000
const MAX_RECONNECT_DELAY = 30000

const handlers: Map<string, Set<EventHandler>> = new Map()

export function connectWS(token: string) {
  if (socket?.readyState === WebSocket.OPEN) return

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/api/v1/ws?token=${token}`

  socket = new WebSocket(url)

  socket.onopen = () => {
    reconnectDelay = 1000
  }

  socket.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data) as Record<string, unknown>
      const event = data.event as string
      if (event) {
        const set = handlers.get(event)
        if (set) set.forEach((fn) => fn(data))
        const all = handlers.get('*')
        if (all) all.forEach((fn) => fn(data))
      }
    } catch {}
  }

  socket.onclose = () => {
    scheduleReconnect(token)
  }

  socket.onerror = () => {
    socket?.close()
  }
}

function scheduleReconnect(token: string) {
  if (reconnectTimer) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connectWS(token)
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY)
  }, reconnectDelay)
}

export function disconnectWS() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  socket?.close()
  socket = null
}

export function onWS(event: string, handler: EventHandler) {
  if (!handlers.has(event)) handlers.set(event, new Set())
  handlers.get(event)!.add(handler)
  return () => {
    handlers.get(event)?.delete(handler)
  }
}

export function sendWS(data: Record<string, unknown>) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(data))
  }
}
