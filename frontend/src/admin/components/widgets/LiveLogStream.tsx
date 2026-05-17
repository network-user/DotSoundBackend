import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from 'react'
import { useQuery } from '@tanstack/react-query'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'
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
const DISPLAY_LIMIT = 300

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
  const [items, setItems] = useState<LogRow[]>([])
  const [, startTransition] = useTransition()
  const deferredItems = useDeferredValue(items)
  const [paused, setPaused] = useState(false)
  const [connected, setConnected] =
    useState(false)
  const [closeCode, setCloseCode] =
    useState<number | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const wsRef = useRef<AdminWs | null>(null)
  const containerRef =
    useRef<HTMLDivElement | null>(null)
  const stickToBottomRef = useRef(true)
  const filtersWrapRef = useRef<HTMLDivElement | null>(null)

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
      onOpen: () => {
        setConnected(true)
        setCloseCode(null)
      },
      onClose: (code) => {
        setConnected(false)
        setCloseCode(code)
      },
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
        startTransition(() => {
          setItems((prev) => {
            const next = [...prev, ...data.items!]
            if (next.length > MAX_BUFFER) {
              return next.slice(next.length - MAX_BUFFER)
            }
            return next
          })
        })
      },
    })
    wsRef.current = ws
    ws.connect()
    ws.subscribe('logs', { filters: filter })
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
    ws.subscribe('logs', { filters: filter })
  }, [filter])

  useEffect(() => {
    if (!stickToBottomRef.current) return
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [deferredItems])

  useEffect(() => {
    if (!filtersOpen) return
    const onClick = (e: MouseEvent) => {
      if (!filtersWrapRef.current) return
      if (!filtersWrapRef.current.contains(e.target as Node)) {
        setFiltersOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFiltersOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [filtersOpen])

  function handleScroll(): void {
    const el = containerRef.current
    if (!el) return
    const distance =
      el.scrollHeight -
      (el.scrollTop + el.clientHeight)
    stickToBottomRef.current = distance < 32
  }

  const activeFilterCount = useMemo(
    () =>
      [filter.service, filter.container, filter.level].filter(
        Boolean,
      ).length,
    [filter.service, filter.container, filter.level],
  )

  const status = useMemo(() => {
    if (!connected) return 'connecting…'
    if (paused) return 'paused'
    return `streaming (${items.length})`
  }, [connected, paused, items.length])

  const displayItems = useMemo(
    () => deferredItems.slice(-DISPLAY_LIMIT),
    [deferredItems],
  )

  const clearChip = (key: keyof LogsFilter) =>
    setFilter((p) => ({ ...p, [key]: undefined }))

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
      {closeCode === 4429 && (
        <div className="admin-warning" role="status">
          Live stream hit the per-admin WebSocket limit. Close other
          admin tabs or drawers and retry.
        </div>
      )}
      <div className="admin-live-log__bar">
        <label className="admin-filter-group__search admin-live-log__search">
          <span className="admin-filter-group__icon" aria-hidden>
            <Icon name="search" size={14} />
          </span>
          <input
            type="search"
            placeholder="Search log lines…"
            value={filter.contains || ''}
            onChange={(e) =>
              setFilter((p) => ({
                ...p,
                contains: e.target.value || undefined,
              }))
            }
            aria-label="Search log lines"
          />
        </label>
        <div
          ref={filtersWrapRef}
          className="admin-live-log__filters"
        >
          <MotionPress
            type="button"
            variant="ghost"
            onClick={() => setFiltersOpen((o) => !o)}
            aria-haspopup="dialog"
            aria-expanded={filtersOpen}
            className={
              activeFilterCount > 0
                ? 'admin-live-log__filters-btn is-active'
                : 'admin-live-log__filters-btn'
            }
          >
            <Icon name="filter" size={14} />
            <span>Filters</span>
            {activeFilterCount > 0 ? (
              <span className="admin-live-log__filters-badge">
                {activeFilterCount}
              </span>
            ) : null}
          </MotionPress>
          {filtersOpen ? (
            <div
              className="admin-live-log__filters-pop"
              role="dialog"
              aria-label="Log filters"
            >
              <label className="admin-live-log__pop-row">
                <span>Service</span>
                <input
                  type="text"
                  placeholder="api, worker…"
                  value={filter.service || ''}
                  onChange={(e) =>
                    setFilter((p) => ({
                      ...p,
                      service: e.target.value || undefined,
                    }))
                  }
                />
              </label>
              <label className="admin-live-log__pop-row">
                <span>Container</span>
                <input
                  type="text"
                  placeholder="container name"
                  value={filter.container || ''}
                  onChange={(e) =>
                    setFilter((p) => ({
                      ...p,
                      container: e.target.value || undefined,
                    }))
                  }
                />
              </label>
              <label className="admin-live-log__pop-row">
                <span>Level</span>
                <select
                  value={filter.level || ''}
                  onChange={(e) =>
                    setFilter((p) => ({
                      ...p,
                      level: e.target.value || undefined,
                    }))
                  }
                >
                  <option value="">any</option>
                  <option value="debug">debug</option>
                  <option value="info">info</option>
                  <option value="warning">warning</option>
                  <option value="error">error</option>
                  <option value="critical">critical</option>
                </select>
              </label>
              <div className="admin-live-log__pop-foot">
                <MotionPress
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    setFilter((p) => ({
                      contains: p.contains,
                    }))
                  }
                >
                  Reset
                </MotionPress>
                <MotionPress
                  type="button"
                  variant="primary"
                  onClick={() => setFiltersOpen(false)}
                >
                  Done
                </MotionPress>
              </div>
            </div>
          ) : null}
        </div>
        <MotionPress
          variant="ghost"
          onClick={() => setPaused((v) => !v)}
        >
          {paused ? 'Resume' : 'Pause'}
        </MotionPress>
        <MotionPress
          variant="ghost"
          onClick={() => setItems([])}
        >
          Clear
        </MotionPress>
        <span className="admin-live-log__status">
          <span
            className={
              connected && !paused
                ? 'admin-live-log__status-dot is-on'
                : 'admin-live-log__status-dot'
            }
            aria-hidden
          />
          {status}
        </span>
      </div>

      {activeFilterCount > 0 ? (
        <div className="admin-live-log__chips">
          {(['service', 'container', 'level'] as const).map((k) =>
            filter[k] ? (
              <button
                key={k}
                type="button"
                className="admin-live-log__chip"
                onClick={() => clearChip(k)}
                aria-label={`Clear ${k}`}
              >
                <span>{k}</span>
                <span className="admin-live-log__chip-val">
                  {filter[k]}
                </span>
                <Icon name="x" size={10} />
              </button>
            ) : null,
          )}
        </div>
      ) : null}

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="admin-log-stream"
        style={{ maxHeight: height }}
      >
        {displayItems.length === 0 && (
          <div className="admin-log-empty">
            Waiting for log entries…
          </div>
        )}
        {displayItems.map((row, idx) => {
          const level = row.labels?.level || 'info'
          return (
            <div
              key={`${row.ts_ns}-${idx}`}
              className={`admin-log-row admin-log-row--${level}`}
            >
              <span
                className={`admin-log-sev admin-log-sev--${level}`}
                aria-hidden
              />
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
          )
        })}
      </div>
    </div>
  )
}
