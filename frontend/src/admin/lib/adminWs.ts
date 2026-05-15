import { useAdminAuth } from '../store/adminAuthStore'
import { getAdminApiPath } from '@/lib/adminPath'

export type AdminWsHandler = (event: {
  channel: string
  data: unknown
}) => void

interface AdminWsOptions {
  onEvent?: AdminWsHandler
  onOpen?: () => void
  onClose?: (code: number) => void
}

export class AdminWs {
  private socket: WebSocket | null = null
  private retryDelay = 1000
  private closed = false
  private reconnectTimer: number | null = null
  private heartbeatTimer: number | null = null
  private subscriptions = new Map<
    string,
    Record<string, unknown>
  >()
  private opts: AdminWsOptions

  constructor(opts: AdminWsOptions = {}) {
    this.opts = opts
  }

  connect(): void {
    if (
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return
    }
    this.closed = false
    this.clearHeartbeatTimer()
    const token =
      useAdminAuth.getState().accessToken
    if (!token) {
      this.scheduleReconnect()
      return
    }
    const proto =
      window.location.protocol === 'https:'
        ? 'wss'
        : 'ws'
    const url = `${proto}://${window.location.host}${getAdminApiPath('/ws')}?token=${encodeURIComponent(
      token,
    )}`
    this.socket = new WebSocket(url)
    this.socket.addEventListener('open', () => {
      this.clearReconnectTimer()
      this.retryDelay = 1000
      this.startHeartbeat()
      for (const [
        channel,
        extras,
      ] of this.subscriptions) {
        this.send({
          type: 'subscribe',
          channel,
          ...extras,
        })
      }
      this.opts.onOpen?.()
    })
    this.socket.addEventListener(
      'message',
      (msg) => {
        try {
          const parsed = JSON.parse(msg.data)
          if (
            parsed?.channel === 'system' &&
            parsed?.data?.type === 'ping'
          ) {
            this.send({ type: 'ping' })
          }
          this.opts.onEvent?.(parsed)
        } catch {
          // ignore malformed payloads
        }
      },
    )
    this.socket.addEventListener(
      'close',
      (event) => {
        this.socket = null
        this.clearHeartbeatTimer()
        this.opts.onClose?.(event.code)
        if (event.code === 4401) {
          useAdminAuth.getState().reset()
          return
        }
        if (event.code === 4429) {
          this.retryDelay = Math.max(
            this.retryDelay,
            10_000,
          )
        }
        if (!this.closed) {
          this.scheduleReconnect()
        }
      },
    )
    this.socket.addEventListener('error', () => {
      try {
        this.socket?.close()
      } catch {
        // ignore
      }
    })
  }

  subscribe(
    channel: string,
    extras: Record<string, unknown> = {},
  ): void {
    this.subscriptions.set(channel, extras)
    this.send({
      type: 'subscribe',
      channel,
      ...extras,
    })
  }

  unsubscribe(channel: string): void {
    this.subscriptions.delete(channel)
    this.send({ type: 'unsubscribe', channel })
  }

  send(payload: Record<string, unknown>): void {
    if (
      this.socket?.readyState === WebSocket.OPEN
    ) {
      this.socket.send(JSON.stringify(payload))
    }
  }

  close(): void {
    this.closed = true
    this.clearReconnectTimer()
    this.clearHeartbeatTimer()
    try {
      this.socket?.close(1000)
    } catch {
      // ignore
    }
    this.socket = null
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null) {
      return
    }
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      if (this.closed) return
      this.retryDelay = Math.min(
        this.retryDelay * 2,
        30_000,
      )
      this.connect()
    }, this.retryDelay)
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer === null) {
      return
    }
    window.clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }

  private startHeartbeat(): void {
    this.clearHeartbeatTimer()
    this.heartbeatTimer = window.setInterval(() => {
      this.send({ type: 'ping' })
    }, 20_000)
  }

  private clearHeartbeatTimer(): void {
    if (this.heartbeatTimer === null) {
      return
    }
    window.clearInterval(this.heartbeatTimer)
    this.heartbeatTimer = null
  }
}
