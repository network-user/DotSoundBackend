import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useQuery } from '@tanstack/react-query'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../../lib/adminApi'
import { AdminWs } from '../../lib/adminWs'

interface LogRow {
  ts_ns: number
  labels: Record<string, string>
  line: string
}

interface LogsFilter {
  service?: string
  container?: string
  level?: string
  contains?: string
}

const MAX_BUFFER = 1000

function fmtTs(ns: number): string {
  return new Date(
    Math.floor(ns / 1_000_000),
  ).toLocaleTimeString()
}

interface Props {
  initialFilter?: LogsFilter
  height?: number | string
}

export function LiveLogStream({
  initialFilter,
  height = '60vh',
}: Props) {
  const [filter, setFilter] =
    useState<LogsFilter>(initialFilter || {})
  const [items, setItems] = useState<LogRow[]>(
    [],
  )
  const [paused, setPaused] = useState(false)
  const [connected, setConnected] =
    useState(false)
  const wsRef = useRef<AdminWs | null>(null)
  const containerRef =
    useRef<HTMLDivElement | null>(null)
  const stickToBottomRef = useRef(true)

  const sourceProbe = useQuery({
    queryKey: ['admin', 'logs', 'source-probe'],
    queryFn: () =>
      adminApi.logsQuery({
        minutes: 1,
        limit: 1,
      }),
    staleTime: 30_000,
  })
  const src = (sourceProbe.data as { source_status?: string })
    ?.source_status

  useEffect(() => {
    const ws = new AdminWs({
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
      onEvent: (event) => {
        if (
          event.channel !== 'logs' ||
          paused
        ) {
          return
        }
        const data = event.data as {
          items?: LogRow[]
          error?: string
        }
        if (!data?.items?.length) return
        setItems((prev) => {
          const next = [...prev, ...data.items!]
          if (next.length > MAX_BUFFER) {
            return next.slice(
              next.length - MAX_BUFFER,
            )
          }
          return next
        })
      },
    })
    wsRef.current = ws
    ws.connect()
    ws.subscribe('logs')
    ws.send({
      type: 'subscribe',
      channel: 'logs',
      filters: filter,
    })
    return () => {
      ws.unsubscribe('logs')
      ws.close()
      wsRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const ws = wsRef.current
    if (!ws) return
    ws.send({
      type: 'logs.update_filter',
      channel: 'logs',
      filters: filter,
    })
  }, [filter])

  useEffect(() => {
    if (!stickToBottomRef.current) return
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [items])

  function handleScroll(): void {
    const el = containerRef.current
    if (!el) return
    const distance =
      el.scrollHeight -
      (el.scrollTop + el.clientHeight)
    stickToBottomRef.current = distance < 32
  }

  const status = useMemo(() => {
    if (!connected) return 'connecting…'
    if (paused) return 'paused'
    return `streaming (${items.length})`
  }, [connected, paused, items.length])

  return (
    <div className="admin-live-log">
      {src === 'disabled' && (
        <div className="admin-warning" role="status">
          Loki is not configured. Set LOKI_URL or use
          DOTSOUND_DEV_LOG_DIR for local file logs (see
          docs/admin/README).
        </div>
      )}
      {src === 'local_dev' && (
        <div className="admin-card__sub" role="status">
          Local dev: tailing log files (DOTSOUND_DEV_LOG_DIR).
        </div>
      )}
      <div className="admin-toolbar admin-toolbar--wrap">
        <input
          type="text"
          placeholder="service"
          value={filter.service || ''}
          onChange={(e) =>
            setFilter((p) => ({
              ...p,
              service:
                e.target.value || undefined,
            }))
          }
        />
        <input
          type="text"
          placeholder="container"
          value={filter.container || ''}
          onChange={(e) =>
            setFilter((p) => ({
              ...p,
              container:
                e.target.value || undefined,
            }))
          }
        />
        <select
          value={filter.level || ''}
          onChange={(e) =>
            setFilter((p) => ({
              ...p,
              level:
                e.target.value || undefined,
            }))
          }
        >
          <option value="">any level</option>
          <option value="debug">debug</option>
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="error">error</option>
          <option value="critical">critical</option>
        </select>
        <input
          type="text"
          placeholder="contains…"
          value={filter.contains || ''}
          onChange={(e) =>
            setFilter((p) => ({
              ...p,
              contains:
                e.target.value || undefined,
            }))
          }
        />
        <Press
          variant="ghost"
          onClick={() =>
            setPaused((v) => !v)
          }
        >
          {paused ? 'Resume' : 'Pause'}
        </Press>
        <Press
          variant="ghost"
          onClick={() => setItems([])}
        >
          Clear
        </Press>
        <span className="admin-live-log__status">
          {status}
        </span>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="admin-log-stream"
        style={{ maxHeight: height }}
      >
        {items.length === 0 && (
          <div className="admin-log-empty">
            Waiting for log entries…
          </div>
        )}
        {items.map((row, idx) => (
          <div
            key={`${row.ts_ns}-${idx}`}
            className={`admin-log-row admin-log-row--${
              row.labels?.level || 'info'
            }`}
          >
            <span className="admin-log-ts">
              {fmtTs(row.ts_ns)}
            </span>
            <span className="admin-log-tag">
              {row.labels?.container ||
                row.labels?.service ||
                'log'}
            </span>
            <span className="admin-log-line">
              {row.line}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
