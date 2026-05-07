import { useAdminAuth } from '../store/adminAuthStore'

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
  private subscriptions = new Map<
    string,
    Record<string, unknown>
  >()
  private opts: AdminWsOptions

  constructor(opts: AdminWsOptions = {}) {
    this.opts = opts
  }

  connect(): void {
    this.closed = false
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
    const url = `${proto}://${window.location.host}/api/v1/admin/ws?token=${encodeURIComponent(
      token,
    )}`
    this.socket = new WebSocket(url)
    this.socket.addEventListener('open', () => {
      this.retryDelay = 1000
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
          this.opts.onEvent?.(parsed)
        } catch {
          // ignore malformed payloads
        }
      },
    )
    this.socket.addEventListener(
      'close',
      (event) => {
        this.opts.onClose?.(event.code)
        if (event.code === 4401) {
          useAdminAuth.getState().reset()
          return
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
    try {
      this.socket?.close(1000)
    } catch {
      // ignore
    }
    this.socket = null
  }

  private scheduleReconnect(): void {
    setTimeout(() => {
      if (this.closed) return
      this.retryDelay = Math.min(
        this.retryDelay * 2,
        30_000,
      )
      this.connect()
    }, this.retryDelay)
  }
}
